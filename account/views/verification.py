"""
Phone number verification (SMS OTP via Termii) and Sign in with Google.

Phone verification runs after the user is signed in (registration or login),
so it never changes the existing email-code flows the apps already depend on:

    POST /auth/phone/send-code/    {"phone_number": "0801..."}   (optional; defaults to the saved number)
    POST /auth/phone/confirm-code/  {"code": "123456"}

Whether the apps must block until the number is verified is controlled by the
PHONE_VERIFICATION_REQUIRED environment flag, surfaced to the apps on the user
payload as `phone_verification_required`. Leave it off until Termii is funded
and the sender ID is approved, so nobody gets locked out.

Google (web + iOS client IDs of findmytaste-cab38 are built in):

    POST /auth/google/  {"id_token": "<Google ID token>"}

The ID token is verified against GOOGLE_OAUTH_CLIENT_IDS (comma-separated).
An existing account with that email signs in; otherwise a customer account is
created, already email-verified, with no usable password.
"""

import logging
import secrets
from datetime import timedelta

from decouple import config
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated

from account.models import User, VerificationCode
from account.serializers import UserSerializer
from helpers.app_scope import check_app_access, get_app_client
from helpers.response.response_format import bad_request_response, success_response
from helpers.termii import TermiiError, normalize_nigerian_phone, send_sms, send_voice_code
from helpers.termii import is_configured as is_sms_configured
from helpers.tokens import TokenManager

logger = logging.getLogger(__name__)

PHONE_CODE_TTL_MINUTES = 10
PHONE_CODE_RESEND_SECONDS = 60
PHONE_CODE_MAX_PER_HOUR = 5
PHONE_CODE_MAX_ATTEMPTS = 5

# Store-review / QA accounts that must be able to get past verification
# without a real SIM. They use the fixed code below and no SMS is sent.
REVIEW_ACCOUNT_EMAILS = {
    'maria1@gmail.com',
    'augustinevickky+11@gmail.com',
    'tester@gmail.com',
    'testing@gmail.com',
}
REVIEW_ACCOUNT_CODE = '123456'

# "Call me instead": calls cost more than SMS, and the resend endpoints work
# without signing in, so calls get their own, tighter limit per account.
VOICE_CODE_RESEND_SECONDS = 60
VOICE_CODE_MAX_PER_HOUR = 3


def voice_call_blocked(user):
    """Reason a code call can't be placed for [user] right now, or None."""
    if not is_sms_configured():
        return 'Calls are not available right now.'
    if cache.get(f'voice_code_cooldown:{user.id}'):
        return 'Please wait a minute before asking for another call.'
    if cache.get(f'voice_code_hourly:{user.id}', 0) >= VOICE_CODE_MAX_PER_HOUR:
        return 'Too many calls requested. Please try again in an hour.'
    return None


def record_voice_call(user):
    cache.set(f'voice_code_cooldown:{user.id}', True, VOICE_CODE_RESEND_SECONDS)
    hourly_key = f'voice_code_hourly:{user.id}'
    cache.set(hourly_key, cache.get(hourly_key, 0) + 1, 60 * 60)


def phone_verification_required():
    # Never block anyone on an SMS code that cannot be sent: the flag only
    # takes effect once Termii is configured.
    from helpers.termii import is_configured
    return config('PHONE_VERIFICATION_REQUIRED', default=False, cast=bool) and is_configured()


def mask_phone(international):
    """2348012345678 -> 0801•••5678"""
    local = local_phone_format(international) or ''
    return f"{local[:4]}•••{local[-4:]}" if len(local) >= 8 else local


def deliver_verification_code(user, code_obj, purpose='login', phone=None, voice=False):
    """
    Send a sign-up or sign-in code, by SMS when phone verification is on,
    otherwise (or if the SMS fails) by email.

    * Sign-up (purpose='register'): SMS to the number entered at sign-up.
      Confirming the code also proves that number (see
      RegisterAccountVerifyAPIView), so no separate phone OTP is needed.
    * Sign-in (purpose='login'): SMS only to an already *verified* number;
      an unverified number may be wrong, so those users still get email.

    With [voice] (the app's "Call me instead"), the same number is phoned
    and the code read out, for networks that never deliver our SMS.

    Review/QA accounts always use email (their fixed codes).
    Returns {'channel': 'sms'|'voice'|'email', 'destination': masked target}.
    """
    from helpers.email import emailService

    use_sms = phone_verification_required() and user.email.lower() not in REVIEW_ACCOUNT_EMAILS
    target = None
    if use_sms:
        if purpose == 'register':
            target = normalize_nigerian_phone(phone or user.phone_number)
        elif user.phone_verified:
            target = normalize_nigerian_phone(user.phone_number)

    if target and voice:
        try:
            send_voice_code(target, code_obj.code)
            code_obj.target = target
            code_obj.save(update_fields=['target', 'updated_at'])
            record_voice_call(user)
            return {'channel': 'voice', 'destination': mask_phone(target)}
        except TermiiError as error:
            logger.warning('Code call to user %s failed, sending SMS instead: %s', user.id, error)

    if target:
        try:
            send_sms(
                target,
                f'Your Find My Taste code is {code_obj.code}. It expires in 10 minutes. '
                'Do not share it with anyone.',
            )
            code_obj.target = target
            code_obj.save(update_fields=['target', 'updated_at'])
            return {'channel': 'sms', 'destination': mask_phone(target)}
        except TermiiError as error:
            logger.warning('SMS code to user %s failed, falling back to email: %s', user.id, error)

    try:
        if purpose == 'login':
            emailService.send_login_verification_code(
                user_email=user.email, user_name=user.full_name,
                verification_code=code_obj.code)
        else:
            emailService.send_verification_code(
                user_email=user.email, user_name=user.full_name,
                verification_code=code_obj.code)
    except Exception as error:
        logger.warning('Email code to user %s failed: %s', user.id, error)
    return {'channel': 'email', 'destination': user.email}


def code_sent_message(delivery, verb='sent'):
    if delivery['channel'] == 'voice':
        return f"We're calling {delivery['destination']} now to read out your code."
    if delivery['channel'] == 'sms':
        return f"A verification code has been {verb} to your phone ({delivery['destination']})."
    return f"A verification code has been {verb} to your email."


def local_phone_format(international):
    """2348012345678 -> 08012345678 (how numbers are stored today)."""
    if international and international.startswith('234') and len(international) == 13:
        return '0' + international[3:]
    return international


class PhoneOTPSendView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Send a phone verification code by SMS",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={'phone_number': openapi.Schema(type=openapi.TYPE_STRING)},
        ),
        responses={200: 'Code sent', 400: 'Invalid number or too many requests'},
    )
    def post(self, request):
        user: User = request.user
        raw_phone = (request.data.get('phone_number') or user.phone_number or '').strip()
        target = normalize_nigerian_phone(raw_phone)
        if not target:
            return bad_request_response(message='Please enter a valid phone number.')

        # Throttle per user: one code a minute, five an hour. SMS costs money
        # and a loop in an app (or abuse) should not drain the Termii wallet.
        cooldown_key = f'phone_otp_cooldown:{user.id}'
        hourly_key = f'phone_otp_hourly:{user.id}'
        if cache.get(cooldown_key):
            return bad_request_response(
                message='Please wait a minute before requesting another code.')
        sent_this_hour = cache.get(hourly_key, 0)
        if sent_this_hour >= PHONE_CODE_MAX_PER_HOUR:
            return bad_request_response(
                message='Too many codes requested. Please try again in an hour.')

        voice = request.data.get('channel') == 'voice'
        if voice:
            blocked = voice_call_blocked(user)
            if blocked:
                return bad_request_response(message=blocked)

        is_review_account = user.email.lower() in REVIEW_ACCOUNT_EMAILS
        # Never starts with 0, so it can also be read out by phone.
        code = REVIEW_ACCOUNT_CODE if is_review_account else str(100000 + secrets.randbelow(900000))

        VerificationCode.objects.filter(user=user, verification_type='phone').delete()
        VerificationCode.objects.create(
            user=user, verification_type='phone', code=code, target=target,
        )

        if not is_review_account:
            try:
                if voice:
                    send_voice_code(target, code)
                    record_voice_call(user)
                else:
                    send_sms(
                        target,
                        f'Your Find My Taste verification code is {code}. '
                        f'It expires in {PHONE_CODE_TTL_MINUTES} minutes. Do not share it with anyone.',
                    )
            except TermiiError as error:
                VerificationCode.objects.filter(user=user, verification_type='phone').delete()
                return bad_request_response(message=str(error))

        cache.set(cooldown_key, True, PHONE_CODE_RESEND_SECONDS)
        cache.set(hourly_key, sent_this_hour + 1, 60 * 60)

        return success_response(
            message=(f"We're calling {mask_phone(target)} now to read out your code."
                     if voice else 'A verification code has been sent to your phone.'),
            data={
                'channel': 'voice' if voice else 'sms',
                'phone_number': local_phone_format(target),
                'expires_in_minutes': PHONE_CODE_TTL_MINUTES,
                'resend_after_seconds': PHONE_CODE_RESEND_SECONDS,
            },
        )


class PhoneOTPVerifyView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Verify the phone code and mark the number verified",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['code'],
            properties={'code': openapi.Schema(type=openapi.TYPE_STRING)},
        ),
        responses={200: 'Phone verified', 400: 'Invalid or expired code'},
    )
    def post(self, request):
        user: User = request.user
        code = str(request.data.get('code') or '').strip()
        if not code:
            return bad_request_response(message='Please enter the code we sent you.')

        attempts_key = f'phone_otp_attempts:{user.id}'
        attempts = cache.get(attempts_key, 0)
        if attempts >= PHONE_CODE_MAX_ATTEMPTS:
            VerificationCode.objects.filter(user=user, verification_type='phone').delete()
            cache.delete(attempts_key)
            return bad_request_response(
                message='Too many wrong attempts. Please request a new code.')

        code_obj = VerificationCode.objects.filter(
            user=user,
            verification_type='phone',
            created_at__gte=timezone.now() - timedelta(minutes=PHONE_CODE_TTL_MINUTES),
        ).order_by('-created_at').first()

        if not code_obj or not secrets.compare_digest(code_obj.code, code):
            cache.set(attempts_key, attempts + 1, PHONE_CODE_TTL_MINUTES * 60)
            return bad_request_response(message='Invalid or expired code.')

        with transaction.atomic():
            user.phone_number = local_phone_format(code_obj.target) or user.phone_number
            user.phone_verified = True
            user.phone_verified_at = timezone.now()
            user.save(update_fields=['phone_number', 'phone_verified', 'phone_verified_at', 'updated_at'])
            VerificationCode.objects.filter(user=user, verification_type='phone').delete()
        cache.delete(attempts_key)

        return success_response(
            message='Your phone number has been verified.',
            data={'user': UserSerializer(user).data},
        )


# OAuth clients of Firebase project findmytaste-cab38 (web client = the
# app's serverClientId; iOS client for the customer iOS app). Public
# identifiers; GOOGLE_OAUTH_CLIENT_IDS overrides them.
DEFAULT_GOOGLE_CLIENT_IDS = ','.join([
    '494095002566-rk5m2jb6h0929psnt7r3cl965f2s84mj.apps.googleusercontent.com',
    '494095002566-13pu781osq2im1qdpeinokcqtqpp9efv.apps.googleusercontent.com',
])


def _google_client_ids():
    raw = config('GOOGLE_OAUTH_CLIENT_IDS', default=DEFAULT_GOOGLE_CLIENT_IDS)
    return [value.strip() for value in raw.split(',') if value.strip()]


def social_sign_in(request, *, provider, email, full_name='', picture=None,
                   email_trusted=True, apple_sub=None):
    """
    Shared by Google and Apple sign-in. Signs in the account for this email
    (or Apple id), or creates a customer account. Returns a DRF response.

    `needs_phone` in the response tells the app to collect (and, when SMS is
    set up, verify) a phone number before continuing, since social sign-ups
    arrive without one.
    """
    user = None
    if apple_sub:
        user = User.objects.filter(apple_sub=apple_sub).first()
    if user is None and email:
        existing = User.objects.filter(email=email).first()
        if existing is not None and not email_trusted:
            # Never hand over an existing account on an unverified email.
            return bad_request_response(
                message='Please sign in with your email and password instead.')
        user = existing
    is_new_user = False

    if user is None:
        if not email:
            return bad_request_response(
                message='We could not get your email from Apple. In Settings > Apple ID > '
                        'Sign-In & Security > Sign in with Apple, remove Find My Taste and try again.')
        # Only the customer app may create accounts this way; vendors and
        # riders need their own onboarding.
        app_client = get_app_client(request)
        if app_client not in (None, 'customer'):
            return bad_request_response(
                message='Please create your account with email first, then sign in.')

        referred_by = None
        referral_code = (request.data.get('referral_code') or '').strip()
        if referral_code:
            referred_by = User.objects.filter(referral_code=referral_code).first()

        user = User(
            email=email,
            full_name=(full_name or '').strip()[:64] or email.split('@')[0],
            role='buyer',
            is_verified=True,
            is_active=True,
            auth_provider=provider,
            profile_image_url=picture or None,
            referred_by=referred_by,
            apple_sub=apple_sub,
        )
        user.set_unusable_password()
        user.save()
        is_new_user = True
    else:
        if not user.is_active:
            return bad_request_response(
                message='This account has been deactivated. Please contact support.')
        access_error = check_app_access(user, request)
        if access_error:
            return bad_request_response(message=access_error)
        updates = []
        if email_trusted and not user.is_verified:
            # The provider has just proven ownership of the email address.
            user.is_verified = True
            updates.append('is_verified')
        if apple_sub and not user.apple_sub:
            user.apple_sub = apple_sub
            updates.append('apple_sub')
        if updates:
            user.save(update_fields=updates + ['updated_at'])

    tokens = TokenManager.get_tokens_for_user(user)
    return success_response(
        message='You are now signed in.',
        data={
            'tokens': tokens,
            'user': UserSerializer(user).data,
            'is_new_user': is_new_user,
            'needs_phone': not (user.phone_number or '').strip(),
            'sms_verification_available': is_sms_configured(),
        },
    )


class GoogleSignInView(generics.GenericAPIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_summary="Sign in or sign up with a Google ID token",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['id_token'],
            properties={
                'id_token': openapi.Schema(type=openapi.TYPE_STRING),
                'referral_code': openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        responses={200: 'Signed in', 400: 'Invalid token or wrong app'},
    )
    def post(self, request):
        token = (request.data.get('id_token') or '').strip()
        if not token:
            return bad_request_response(message='Google sign-in failed. Please try again.')

        client_ids = _google_client_ids()
        if not client_ids:
            return bad_request_response(message='Google sign-in is not available yet.')

        try:
            from google.auth.transport import requests as google_requests
            from google.oauth2 import id_token as google_id_token

            info = google_id_token.verify_oauth2_token(token, google_requests.Request())
        except Exception as error:
            logger.warning('Google ID token rejected: %s', error)
            return bad_request_response(message='Google sign-in failed. Please try again.')

        if info.get('aud') not in client_ids:
            logger.warning('Google ID token for unexpected audience %s', info.get('aud'))
            return bad_request_response(message='Google sign-in failed. Please try again.')
        if not info.get('email') or not info.get('email_verified'):
            return bad_request_response(
                message='Your Google account email is not verified.')

        return social_sign_in(
            request,
            provider='google',
            email=info['email'].lower(),
            full_name=info.get('name') or '',
            picture=info.get('picture'),
        )


APPLE_ISSUER = 'https://appleid.apple.com'
APPLE_KEYS_URL = 'https://appleid.apple.com/auth/keys'
_apple_jwks_client = None


def _apple_client_ids():
    raw = config('APPLE_CLIENT_IDS', default='com.findmytaste.customer')
    return [value.strip() for value in raw.split(',') if value.strip()]


def verify_apple_identity_token(token):
    """Check Apple's signature, issuer, audience and expiry; return the claims."""
    import jwt

    global _apple_jwks_client
    if _apple_jwks_client is None:
        # Caches Apple's public keys between requests.
        _apple_jwks_client = jwt.PyJWKClient(APPLE_KEYS_URL)
    signing_key = _apple_jwks_client.get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=['RS256'],
        audience=_apple_client_ids(),
        issuer=APPLE_ISSUER,
    )


class AppleSignInView(generics.GenericAPIView):
    """
    POST /auth/apple/  {"identity_token": "...", "full_name": "Ada Obi"}

    Sign in with Apple (required by the App Store whenever Google sign-in is
    offered on iOS). Apple sends the user's name only on the very first
    sign-in, so the app forwards it as `full_name`.
    """

    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_summary="Sign in or sign up with an Apple identity token",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['identity_token'],
            properties={
                'identity_token': openapi.Schema(type=openapi.TYPE_STRING),
                'full_name': openapi.Schema(type=openapi.TYPE_STRING),
                'referral_code': openapi.Schema(type=openapi.TYPE_STRING),
            },
        ),
        responses={200: 'Signed in', 400: 'Invalid token or wrong app'},
    )
    def post(self, request):
        token = (request.data.get('identity_token') or '').strip()
        if not token:
            return bad_request_response(message='Apple sign-in failed. Please try again.')
        try:
            claims = verify_apple_identity_token(token)
        except Exception as error:
            logger.warning('Apple identity token rejected: %s', error)
            return bad_request_response(message='Apple sign-in failed. Please try again.')

        sub = claims.get('sub')
        if not sub:
            return bad_request_response(message='Apple sign-in failed. Please try again.')
        email = (claims.get('email') or '').strip().lower() or None
        email_verified = str(claims.get('email_verified', '')).lower() == 'true'

        return social_sign_in(
            request,
            provider='apple',
            email=email,
            full_name=request.data.get('full_name') or '',
            email_trusted=email_verified,
            apple_sub=sub,
        )
