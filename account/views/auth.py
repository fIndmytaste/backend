from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from rest_framework import generics
from rest_framework.permissions import AllowAny
from account.models import User, VerificationCode
from account.serializers import LoginSerializer, PasswordResetConfirmSerializer, PasswordResetRequestSerializer, RegisterSerializer, RegisterVendorSerializer, RegisterVerifySerializer, UserSerializer
from helpers.response.response_format import bad_request_response, success_response
from helpers.tokens import TokenManager
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

class LoginAPIView(generics.GenericAPIView):
    """
    View to handle user login via email.
    """
    permission_classes = [AllowAny]  # This view can be accessed without authentication
    serializer_class = LoginSerializer

    @swagger_auto_schema(
        operation_description="Log in a user with email and password.",
        operation_summary="Log in a user by providing email and password",
        request_body=LoginSerializer,
        responses={200: 'Login successful', 400: 'Invalid credentials or inactive user'}
    )
    def post(self, request, *args, **kwargs):
        """
        POST request to log in the user using email and password.

        **Request Body:**
        - identifier: Email or university ID of the user.
        - password: Password of the user.

        **Responses:**
        - 200: Successfully logged in, returning tokens and user data.
        - 400: Invalid credentials or inactive user.
        """
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid(raise_exception=True):
            email = serializer.validated_data['email']
            password = serializer.validated_data['password']

            # Try to authenticate the user with email or university_id
            user = authenticate(request, email=email, password=password)
            if user is not None and user.is_active:
                # User found and is active
                valid_user = User.objects.get(pk=user.id)
                tokens = TokenManager.get_tokens_for_user(user)
                response_data = {
                    "tokens": tokens,
                    'user': UserSerializer(valid_user).data
                }
                return success_response(message='Login successfully.', data=response_data)
            else:
                # Invalid credentials or inactive user
                return bad_request_response(message='Invalid credentials or user is not active.')


class RegisterAPIView(generics.GenericAPIView):
    """
    View to register a new user.
    """
    serializer_class = RegisterSerializer

    @swagger_auto_schema(
        operation_description="Register a new user and return the created user data and tokens.",
        operation_summary="Register a new user and return their details and authentication tokens.",
        request_body=RegisterSerializer,
        responses={201: 'Account created successfully.', 400: 'Validation errors or bad input data'}
    )
    def post(self, request, *args, **kwargs):
        """
        POST request to register a new user.

        **Request Body:**
        - full_name: The full name of the user.
        - email: The email of the user.
        - password: The password for the new account.

        **Responses:**
        - 201: Successfully created the account with user data and tokens.
        - 400: Validation errors or bad input data.
        """
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        valid_user = User.objects.get(pk=user.id)
        # tokens = TokenManager.get_tokens_for_user(user)
        # response_data = {
        #     "tokens": tokens,
        #     'user': UserSerializer(valid_user).data
        # }
         # Generate six code
        code_obj = VerificationCode.objects.create(
            user=valid_user,
            verification_type='email'
        )

        #!TODO Send verification code to email (not implemented here)

        return success_response(
            # add message that verification code has been sent to their email
            message=f'Verification code has been sent to your email. :: {code_obj.code}',

        )

class RegisterVendorAPIView(generics.GenericAPIView):
    """
    View to register a new vendor.
    """
    serializer_class = RegisterVendorSerializer

    @swagger_auto_schema(
        operation_description="Register a new vendor and return the created user data and tokens.",
        operation_summary="Register a new vendor and return vendor details and authentication tokens.",
        request_body=RegisterVendorSerializer,
        responses={201: 'Vendor account created successfully.', 400: 'Validation errors or bad input data'}
    )
    def post(self, request, *args, **kwargs):
        """
        POST request to register a new vendor.

        **Request Body:**
        - full_name: The vendor's full name.
        - email: The vendor's email.
        - password: The vendor's password.

        **Responses:**
        - 201: Successfully created the vendor account with user data and tokens.
        - 400: Validation errors or bad input data.
        """
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        valid_user = User.objects.get(pk=user.id)
        # tokens = TokenManager.get_tokens_for_user(user)
        # response_data = {
        #     "tokens": tokens,
        #     'user': UserSerializer(valid_user).data
        # }
        
        # Generate six code
        code_obj = VerificationCode.objects.create(
            user=valid_user,
            verification_type='email'
        )

        #!TODO Send verification code to email (not implemented here)

        return success_response(
            # add message that verification code has been sent to their email
            message=f'Verification code has been sent to your email. :: {code_obj.code}',

        )



class RegisterAccountVerifyAPIView(generics.GenericAPIView):
    """
    View to register a new vendor.
    """
    serializer_class = RegisterVerifySerializer

    @swagger_auto_schema(
    )
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data['code']

       
        # Generate six code
        try:
            code_obj = VerificationCode.objects.get( code=code,verification_type='email' )
        except:
            return bad_request_response(
                message='Invalid or expired verification code.'
            )

        if not code_obj.is_active:
            return bad_request_response(
                message='Invalid or expired verification code.'
            )
        
        user = code_obj.user
        user.is_verified = True
        user.is_active = True
        user.save()
        code_obj.delete()
        return success_response(
            message='Account verified successfully.'
        )




class PasswordResetConfirmView(generics.GenericAPIView):
    """
    View to confirm the password reset using the provided token.
    """
    serializer_class = PasswordResetConfirmSerializer

    @swagger_auto_schema(
        operation_description="Reset the user's password using the token sent via email.",
        operation_summary="Confirm the password reset using the provided token and new password.",
        request_body=PasswordResetConfirmSerializer,
        responses={200: 'Password successfully reset.', 400: 'Invalid token or user ID.'}
    )
    def post(self, request, uidb64, token, *args, **kwargs):
        """
        POST request to confirm the password reset.

        **Request Body:**
        - new_password: The new password for the user.

        **Responses:**
        - 200: Successfully reset the password.
        - 400: Invalid or expired token.
        """
        try:
            # Decode the user ID from the URL
            uid = urlsafe_base64_decode(uidb64).decode()
            user = get_user_model().objects.get(pk=uid)
        except (ValueError, TypeError, get_user_model().DoesNotExist):
            return bad_request_response(message="Invalid token or user ID.")

        # Validate the token
        if not default_token_generator.check_token(user, token):
            return bad_request_response(message="Invalid or expired token.")

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_password = serializer.validated_data['new_password']

        # Set the new password and save
        user.set_password(new_password)
        user.save()

        return success_response(message="Password successfully reset.")


class PasswordResetRequestView(generics.GenericAPIView):
    """
    View to handle the password reset request.
    """
    serializer_class = PasswordResetRequestSerializer

    @swagger_auto_schema(
        operation_description="Send a password reset link to the user's email.",
        operation_summary="Request a password reset link to be sent to the user's email.",
        request_body=PasswordResetRequestSerializer,
        responses={200: 'Password reset email sent.', 400: 'User with this email does not exist.'}
    )
    def post(self, request, *args, **kwargs):
        """
        POST request to initiate the password reset process.

        **Request Body:**
        - email: The email of the user requesting the password reset.

        **Responses:**
        - 200: Successfully sent the password reset email.
        - 400: User with this email does not exist.
        """
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        user_model = get_user_model()

        try:
            user = user_model.objects.get(email=email)
        except user_model.DoesNotExist:
            return bad_request_response(message="User with this email does not exist.")

        # Generate password reset token and uid
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(user.pk.encode())

        # Construct the reset link
        reset_link = f"/password-reset/{uid}/{token}/"

        # Send the email with the reset link (not implemented here)
        subject = "Password Reset Request"

        return success_response(message="Password reset email sent.")
