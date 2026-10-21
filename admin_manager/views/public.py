"""
App-facing endpoints for features configured on the admin dashboard.

    GET  support/contact-options/      how to reach support (live chat / WhatsApp)
    GET  email/unsubscribe/<token>/    one-click opt-out from email campaigns
    GET/POST vendor/auto-payout/       vendor asks for (or stops) automatic payouts
    GET  riders/rewards/progress/      rider's progress towards active rewards
"""

from urllib.parse import quote

from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import escape
from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated

from account.models import Rider, User, Vendor
from admin_manager.models import SupportSettings
from helpers.response.response_format import bad_request_response, success_response


class SupportContactOptionsView(generics.GenericAPIView):
    permission_classes = [AllowAny]

    def get(self, request):
        settings_obj = SupportSettings.get_settings()
        whatsapp_url = None
        if settings_obj.whatsapp_enabled and settings_obj.whatsapp_number:
            whatsapp_url = f"https://wa.me/{settings_obj.whatsapp_number}"
            if settings_obj.whatsapp_message:
                whatsapp_url += f"?text={quote(settings_obj.whatsapp_message)}"
        return success_response(data={
            'live_chat_enabled': settings_obj.live_chat_enabled,
            'whatsapp_enabled': bool(whatsapp_url),
            'whatsapp_url': whatsapp_url,
            'whatsapp_number': settings_obj.whatsapp_number or None,
            'support_email': settings_obj.support_email or None,
            'support_phone': settings_obj.support_phone or None,
        })


class EmailUnsubscribeView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, token):
        from admin_manager.campaigns import user_id_from_unsubscribe_token

        user_id = user_id_from_unsubscribe_token(token)
        user = User.objects.filter(id=user_id).first() if user_id else None
        if user is None:
            return _page("This link is not valid.",
                         "Please use the unsubscribe link from a recent email.", status=400)
        if user.marketing_emails_opt_in:
            user.marketing_emails_opt_in = False
            user.save(update_fields=['marketing_emails_opt_in', 'updated_at'])
        return _page(
            "You're unsubscribed",
            f"{escape(user.email)} will no longer receive promotional emails from Find My Taste. "
            "You'll still get emails about your account and orders.",
        )


def _page(title, message, status=200):
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title></head>
<body style="margin:0;background:#EEF7F3;font-family:'Segoe UI',Helvetica,Arial,sans-serif;color:#1F2937">
<div style="max-width:480px;margin:64px auto;background:#fff;border-radius:16px;overflow:hidden">
<div style="background:#02C897;padding:24px;text-align:center;color:#fff;font:700 26px Georgia,serif">Find my Taste</div>
<div style="padding:28px 28px 32px"><h1 style="font-size:20px;margin:0 0 12px">{escape(title)}</h1>
<p style="margin:0;line-height:1.6;color:#4B5563">{message}</p></div></div></body></html>"""
    return HttpResponse(html, status=status)


class VendorAutoPayoutRequestView(generics.GenericAPIView):
    """
    GET  -> current state.
    POST {"enabled": true}  asks an admin to switch automatic payouts on.
    POST {"enabled": false} switches them off (or withdraws the request) at once.
    """

    permission_classes = [IsAuthenticated]

    def _vendor(self, request):
        return Vendor.objects.select_related('user').filter(user=request.user).first()

    def get(self, request):
        from admin_manager.views.growth import vendor_auto_payout_state
        vendor = self._vendor(request)
        if vendor is None:
            return bad_request_response(message="Only vendors can use automatic payouts.", status_code=403)
        return success_response(data=vendor_auto_payout_state(vendor))

    def post(self, request):
        from admin_manager.views.growth import vendor_auto_payout_state
        vendor = self._vendor(request)
        if vendor is None:
            return bad_request_response(message="Only vendors can use automatic payouts.", status_code=403)
        enabled = request.data.get('enabled')
        if not isinstance(enabled, bool):
            return bad_request_response(message="'enabled' must be true or false.")

        if enabled:
            if vendor.auto_payout_enabled:
                return success_response(
                    message="Automatic payouts are already on.",
                    data=vendor_auto_payout_state(vendor))
            state = vendor_auto_payout_state(vendor)
            if not state['has_bank_details']:
                return bad_request_response(
                    message="Add your bank account first so we know where to send payouts.")
            vendor.auto_payout_requested = True
            vendor.auto_payout_requested_at = timezone.now()
            vendor.save(update_fields=['auto_payout_requested', 'auto_payout_requested_at', 'updated_at'])
            message = "Request sent. We'll switch on automatic payouts for you shortly."
        else:
            vendor.auto_payout_enabled = False
            vendor.auto_payout_requested = False
            vendor.save(update_fields=['auto_payout_enabled', 'auto_payout_requested', 'updated_at'])
            message = "Automatic payouts are off. You can still request payouts yourself."

        return success_response(message=message, data=vendor_auto_payout_state(vendor))


class RiderRewardProgressView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from admin_manager.rewards import rider_reward_progress

        rider = Rider.objects.filter(user=request.user).first()
        if rider is None:
            return bad_request_response(message="Only riders have rewards.", status_code=403)
        return success_response(data=rider_reward_progress(rider))
