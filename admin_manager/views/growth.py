"""
Admin dashboard: operations and growth tools.

    Riders     POST riders/<id>/name-lock/                  allow / lock one name change
    Orders     POST orders/<id>/accept-for-vendor/          accept a stuck order for the vendor
    Vendors    GET/POST vendor/<id>/auto-payout/            automatic payouts on/off
               GET  auto-payout-requests/                   vendors waiting for approval
    Apps       GET/POST app-versions/, GET/PUT/DELETE app-versions/<id>/
    Support    GET/PUT support-settings/
    Email      GET/POST email-campaigns/, GET/PUT/DELETE email-campaigns/<id>/,
               POST email-campaigns/<id>/send/, POST email-campaigns/<id>/test/
    Rewards    GET/POST rider-rewards/, GET/PUT/DELETE rider-rewards/<id>/,
               GET rider-rewards/<id>/awards/

Each group is gated on the matching custom-admin page permission, so staff
only reach what they have been granted (superusers and admins reach all).
"""

import logging

from django.db import transaction
from django.utils import timezone
from rest_framework import generics, serializers
from rest_framework.permissions import BasePermission

from account.models import Rider, StaffPagePermission, Vendor
from admin_manager.models import (
    AppVersionPolicy,
    EmailCampaign,
    RiderRewardAward,
    RiderRewardProgram,
    SupportSettings,
)
from helpers.response.response_format import (
    bad_request_response,
    paginate_success_response_with_serializer,
    success_response,
)
from product.models import Order

logger = logging.getLogger(__name__)


def page_permission(page):
    """Permission class: superuser/admin, or staff granted `page`."""

    class _HasPage(BasePermission):
        message = "You do not have permission to manage this page."

        def has_permission(self, request, view):
            user = request.user
            if not (user and user.is_authenticated):
                return False
            if user.is_superuser or getattr(user, 'role', None) == 'admin':
                return True
            return bool(user.is_staff) and StaffPagePermission.objects.filter(
                user=user, page=page,
            ).exists()

    _HasPage.__name__ = f"HasPage_{page.replace('-', '_')}"
    return _HasPage


# ─────────────────────────────────────────────────────────────────────────────
# Rider name lock
# ─────────────────────────────────────────────────────────────────────────────

class AdminRiderNameLockView(generics.GenericAPIView):
    """GET/POST riders/<id>/name-lock/  {"allowed": true|false}"""

    permission_classes = [page_permission('riders')]

    def _state(self, rider):
        return {
            'rider_id': str(rider.id),
            'full_name': rider.user.full_name or '',
            'name_change_allowed': rider.name_change_allowed,
            'can_change_name': rider.can_change_name(),
        }

    def _rider(self, rider_id):
        return Rider.objects.select_related('user').filter(id=rider_id).first()

    def get(self, request, id):
        rider = self._rider(id)
        if rider is None:
            return bad_request_response(message="Rider not found.", status_code=404)
        return success_response(data=self._state(rider))

    def post(self, request, id):
        rider = self._rider(id)
        if rider is None:
            return bad_request_response(message="Rider not found.", status_code=404)
        allowed = request.data.get('allowed')
        if not isinstance(allowed, bool):
            return bad_request_response(message="'allowed' must be true or false.")
        rider.name_change_allowed = allowed
        rider.save(update_fields=['name_change_allowed'])
        return success_response(
            message=(
                "Rider can now change their name once."
                if allowed else "Rider's name is locked."
            ),
            data=self._state(rider),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Accept an order on the vendor's behalf
# ─────────────────────────────────────────────────────────────────────────────

class AdminAcceptOrderForVendorView(generics.GenericAPIView):
    """
    POST orders/<id>/accept-for-vendor/

    For a paid order still waiting on the vendor. Runs the vendor's own accept
    path (customer notified, order opened to riders) and tells the vendor it
    was accepted for them.
    """

    permission_classes = [page_permission('orders')]

    def post(self, request, id):
        from vendor.views import accept_pending_order

        order = Order.objects.select_related('vendor', 'vendor__user', 'user').filter(id=id).first()
        if order is None:
            return bad_request_response(message="Order not found.", status_code=404)
        if order.status != 'pending':
            return bad_request_response(
                message=f"Only orders waiting for the vendor can be accepted (this one is '{order.status}').")
        if order.payment_status != 'paid':
            return bad_request_response(
                message="This order has not been paid for, so it cannot be accepted yet.")

        accepted, message = accept_pending_order(order, accepted_by_admin=request.user)
        if not accepted:
            return bad_request_response(message=message)

        logger.info(
            "Admin %s accepted order %s on behalf of vendor %s",
            request.user.id, order.id, order.vendor_id,
        )
        order.refresh_from_db()
        return success_response(
            message="Order accepted for the vendor. Riders can now see it.",
            data={
                'order_id': str(order.id),
                'status': order.status,
                'delivery_status': order.delivery_status,
            },
        )


# ─────────────────────────────────────────────────────────────────────────────
# Vendor automatic payouts
# ─────────────────────────────────────────────────────────────────────────────

def vendor_auto_payout_state(vendor):
    return {
        'vendor_id': str(vendor.id),
        'vendor_name': vendor.name,
        'auto_payout_enabled': vendor.auto_payout_enabled,
        'auto_payout_requested': vendor.auto_payout_requested,
        'auto_payout_requested_at': (
            vendor.auto_payout_requested_at.isoformat()
            if vendor.auto_payout_requested_at else None
        ),
        'has_bank_details': bool(
            (vendor.bank_account and vendor.bank_name)
            or (vendor.user.bank_account and vendor.user.bank_name)
        ),
    }


class AdminVendorAutoPayoutView(generics.GenericAPIView):
    """GET/POST vendor/<id>/auto-payout/  {"enabled": true|false}"""

    permission_classes = [page_permission('vendor')]

    def _vendor(self, vendor_id):
        return Vendor.objects.select_related('user').filter(id=vendor_id).first()

    def get(self, request, vendor_id):
        vendor = self._vendor(vendor_id)
        if vendor is None:
            return bad_request_response(message="Vendor not found.", status_code=404)
        return success_response(data=vendor_auto_payout_state(vendor))

    def post(self, request, vendor_id):
        vendor = self._vendor(vendor_id)
        if vendor is None:
            return bad_request_response(message="Vendor not found.", status_code=404)
        enabled = request.data.get('enabled')
        if not isinstance(enabled, bool):
            return bad_request_response(message="'enabled' must be true or false.")
        vendor.auto_payout_enabled = enabled
        # Approving or declining settles any pending request.
        vendor.auto_payout_requested = False
        vendor.save(update_fields=['auto_payout_enabled', 'auto_payout_requested', 'updated_at'])

        try:
            from account.models import Notification
            from helpers.push_notification import notification_helper
            title = 'Automatic payouts on' if enabled else 'Automatic payouts off'
            body = (
                'Your cleared balance will now be paid to your bank account automatically.'
                if enabled else
                'Automatic payouts are off. You can still request a payout any time.'
            )
            Notification.objects.create(user=vendor.user, title=title, content=body)
            notification_helper.send_to_user_async(
                user=vendor.user, title=title, body=body, data={'type': 'auto_payout'})
        except Exception as error:
            logger.warning("Auto-payout notification failed for vendor %s: %s", vendor.id, error)

        return success_response(
            message="Automatic payouts enabled." if enabled else "Automatic payouts disabled.",
            data=vendor_auto_payout_state(vendor),
        )


class AdminAutoPayoutRequestListView(generics.GenericAPIView):
    """GET auto-payout-requests/  vendors who asked for automatic payouts."""

    permission_classes = [page_permission('vendor')]

    def get(self, request):
        vendors = Vendor.objects.select_related('user').filter(
            auto_payout_requested=True).order_by('auto_payout_requested_at')
        return success_response(data=[vendor_auto_payout_state(v) for v in vendors])


# ─────────────────────────────────────────────────────────────────────────────
# App version policies
# ─────────────────────────────────────────────────────────────────────────────

class AppVersionPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = AppVersionPolicy
        fields = [
            'id', 'app', 'platform', 'latest_version', 'minimum_version',
            'store_url', 'release_notes', 'is_active', 'updated_at',
        ]
        read_only_fields = ['id', 'updated_at']

    def _check_version(self, value):
        from helpers.app_version import parse_version
        if value and parse_version(value) is None:
            raise serializers.ValidationError("Use a version like 1.0.4")
        return value

    def validate_latest_version(self, value):
        if not value:
            raise serializers.ValidationError("Latest version is required.")
        return self._check_version(value.strip())

    def validate_minimum_version(self, value):
        return self._check_version((value or '').strip())

    def validate(self, attrs):
        from helpers.app_version import parse_version
        latest = attrs.get('latest_version', getattr(self.instance, 'latest_version', ''))
        minimum = attrs.get('minimum_version', getattr(self.instance, 'minimum_version', ''))
        if minimum and latest and parse_version(minimum) > parse_version(latest):
            raise serializers.ValidationError(
                {'minimum_version': "Minimum version cannot be newer than the latest version."})
        store_url = attrs.get('store_url', getattr(self.instance, 'store_url', ''))
        if minimum and not store_url:
            # A forced update with nowhere to update from would lock users out.
            raise serializers.ValidationError(
                {'store_url': "Add the store link before requiring an update."})
        return attrs


class AdminAppVersionListView(generics.GenericAPIView):
    permission_classes = [page_permission('app-settings')]

    def get(self, request):
        return success_response(
            data=AppVersionPolicySerializer(AppVersionPolicy.objects.all(), many=True).data)

    def post(self, request):
        app = request.data.get('app')
        platform = request.data.get('platform')
        instance = AppVersionPolicy.objects.filter(app=app, platform=platform).first()
        serializer = AppVersionPolicySerializer(instance, data=request.data, partial=instance is not None)
        if not serializer.is_valid():
            return bad_request_response(message=_first_error(serializer.errors), data=serializer.errors)
        policy = serializer.save(updated_by=request.user)
        return success_response(message="App version saved.", data=AppVersionPolicySerializer(policy).data)


class AdminAppVersionDetailView(generics.GenericAPIView):
    permission_classes = [page_permission('app-settings')]

    def put(self, request, id):
        policy = AppVersionPolicy.objects.filter(id=id).first()
        if policy is None:
            return bad_request_response(message="Not found.", status_code=404)
        serializer = AppVersionPolicySerializer(policy, data=request.data, partial=True)
        if not serializer.is_valid():
            return bad_request_response(message=_first_error(serializer.errors), data=serializer.errors)
        policy = serializer.save(updated_by=request.user)
        return success_response(message="App version saved.", data=AppVersionPolicySerializer(policy).data)

    def delete(self, request, id):
        AppVersionPolicy.objects.filter(id=id).delete()
        return success_response(message="App version removed.")


# ─────────────────────────────────────────────────────────────────────────────
# Support settings
# ─────────────────────────────────────────────────────────────────────────────

class SupportSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportSettings
        fields = [
            'whatsapp_number', 'whatsapp_message', 'whatsapp_enabled',
            'live_chat_enabled', 'support_email', 'support_phone', 'updated_at',
        ]
        read_only_fields = ['updated_at']

    def validate_whatsapp_number(self, value):
        from helpers.termii import normalize_nigerian_phone
        value = (value or '').strip()
        if not value:
            return ''
        normalized = normalize_nigerian_phone(value)
        if not normalized:
            raise serializers.ValidationError("Enter a valid phone number, e.g. 08012345678.")
        return normalized


class AdminSupportSettingsView(generics.GenericAPIView):
    permission_classes = [page_permission('app-settings')]

    def get(self, request):
        return success_response(data=SupportSettingsSerializer(SupportSettings.get_settings()).data)

    def put(self, request):
        serializer = SupportSettingsSerializer(
            SupportSettings.get_settings(), data=request.data, partial=True)
        if not serializer.is_valid():
            return bad_request_response(message=_first_error(serializer.errors), data=serializer.errors)
        serializer.save()
        return success_response(message="Support settings saved.", data=serializer.data)


# ─────────────────────────────────────────────────────────────────────────────
# Email campaigns
# ─────────────────────────────────────────────────────────────────────────────

class EmailCampaignSerializer(serializers.ModelSerializer):
    audience_size = serializers.SerializerMethodField()
    # Text, not URLField: "findmytaste.com.ng/promo" is accepted and saved
    # with https:// in front instead of being rejected.
    cta_url = serializers.CharField(max_length=500, required=False, allow_blank=True)

    class Meta:
        model = EmailCampaign
        fields = [
            'id', 'subject', 'preheader', 'heading', 'body', 'cta_label', 'cta_url',
            'audience', 'status', 'recipient_count', 'sent_count', 'failed_count',
            'last_error', 'sent_at', 'created_at', 'updated_at', 'audience_size',
        ]
        read_only_fields = [
            'id', 'status', 'recipient_count', 'sent_count', 'failed_count',
            'last_error', 'sent_at', 'created_at', 'updated_at', 'audience_size',
        ]

    def get_audience_size(self, obj):
        # Only drafts need a live estimate; sent campaigns keep their count.
        if obj.status != 'draft':
            return obj.recipient_count
        return obj.recipients().count()

    def validate_cta_url(self, value):
        from django.core.validators import URLValidator
        from django.core.exceptions import ValidationError as DjangoValidationError
        from admin_manager.campaigns import button_url

        value = button_url(value)
        if value:
            try:
                URLValidator(schemes=['http', 'https'])(value)
            except DjangoValidationError:
                raise serializers.ValidationError(
                    "Enter a full web link, like https://findmytaste.com.ng/offers.")
        return value

    def validate(self, attrs):
        label = attrs.get('cta_label', getattr(self.instance, 'cta_label', ''))
        url = attrs.get('cta_url', getattr(self.instance, 'cta_url', ''))
        if bool(label) != bool(url):
            raise serializers.ValidationError(
                {'cta_url': "Give the button both a label and a link, or leave both empty."})
        return attrs


class AdminEmailCampaignListView(generics.GenericAPIView):
    permission_classes = [page_permission('email-campaigns')]

    def get(self, request):
        return paginate_success_response_with_serializer(
            request, EmailCampaignSerializer, EmailCampaign.objects.all(),
            page_size=int(request.GET.get('page_size', 20)),
        )

    def post(self, request):
        serializer = EmailCampaignSerializer(data=request.data)
        if not serializer.is_valid():
            return bad_request_response(message=_first_error(serializer.errors), data=serializer.errors)
        campaign = serializer.save(created_by=request.user)
        return success_response(message="Campaign saved as draft.", data=EmailCampaignSerializer(campaign).data)


class AdminEmailCampaignDetailView(generics.GenericAPIView):
    permission_classes = [page_permission('email-campaigns')]

    def _campaign(self, id):
        return EmailCampaign.objects.filter(id=id).first()

    def get(self, request, id):
        campaign = self._campaign(id)
        if campaign is None:
            return bad_request_response(message="Campaign not found.", status_code=404)
        return success_response(data=EmailCampaignSerializer(campaign).data)

    def put(self, request, id):
        campaign = self._campaign(id)
        if campaign is None:
            return bad_request_response(message="Campaign not found.", status_code=404)
        if campaign.status != 'draft':
            return bad_request_response(message="Only drafts can be edited.")
        serializer = EmailCampaignSerializer(campaign, data=request.data, partial=True)
        if not serializer.is_valid():
            return bad_request_response(message=_first_error(serializer.errors), data=serializer.errors)
        campaign = serializer.save()
        return success_response(message="Campaign saved.", data=EmailCampaignSerializer(campaign).data)

    def delete(self, request, id):
        campaign = self._campaign(id)
        if campaign is None:
            return bad_request_response(message="Campaign not found.", status_code=404)
        if campaign.status == 'sending':
            return bad_request_response(message="This campaign is sending and cannot be deleted.")
        campaign.delete()
        return success_response(message="Campaign deleted.")


class AdminEmailCampaignSendView(generics.GenericAPIView):
    """POST email-campaigns/<id>/send/  send a draft to its whole audience."""

    permission_classes = [page_permission('email-campaigns')]

    def post(self, request, id):
        from admin_manager.campaigns import queue_campaign

        with transaction.atomic():
            campaign = EmailCampaign.objects.select_for_update().filter(id=id).first()
            if campaign is None:
                return bad_request_response(message="Campaign not found.", status_code=404)
            if campaign.status != 'draft':
                return bad_request_response(message="This campaign has already been sent.")
            recipient_count = campaign.recipients().count()
            if recipient_count == 0:
                return bad_request_response(message="Nobody in this audience can receive emails.")
            campaign.status = 'sending'
            campaign.recipient_count = recipient_count
            campaign.sent_count = 0
            campaign.failed_count = 0
            campaign.last_error = ''
            campaign.save()

        queue_campaign(campaign.id)
        return success_response(
            message=f"Sending to {recipient_count} people. This can take a few minutes.",
            data=EmailCampaignSerializer(campaign).data,
        )


class AdminEmailCampaignTestView(generics.GenericAPIView):
    """POST email-campaigns/<id>/test/  {"email": "..."}  send one preview copy."""

    permission_classes = [page_permission('email-campaigns')]

    def post(self, request, id):
        from admin_manager.campaigns import send_campaign_email

        campaign = EmailCampaign.objects.filter(id=id).first()
        if campaign is None:
            return bad_request_response(message="Campaign not found.", status_code=404)
        email = (request.data.get('email') or request.user.email or '').strip()
        try:
            serializers.EmailField().run_validation(email)
        except serializers.ValidationError:
            return bad_request_response(message="Enter a valid email address.")

        sent = send_campaign_email(campaign, email, name=request.user.full_name, unsubscribe_url=None)
        if not sent:
            return bad_request_response(message="The test email could not be sent. Check the email settings.")
        return success_response(message=f"Test email sent to {email}.")


class AdminContactsExportView(generics.GenericAPIView):
    """
    GET email-campaigns/contacts.csv?audience=customers|vendors|riders|all
                                    &include_unsubscribed=1

    Customers, vendors and riders as a CSV ready to import into Brevo (or any
    mailing tool). Column names are the ones Brevo maps automatically: EMAIL,
    FIRSTNAME, LASTNAME and SMS (phone with country code). People who
    unsubscribed from promotional emails are left out unless asked for.
    """

    permission_classes = [page_permission('email-campaigns')]
    ROLES = {'customers': 'buyer', 'vendors': 'vendor', 'riders': 'rider'}
    ROLE_LABELS = {'buyer': 'customer', 'vendor': 'vendor', 'rider': 'rider'}

    def get(self, request):
        import csv
        from django.http import HttpResponse
        from account.models import User
        from helpers.termii import normalize_nigerian_phone

        audience = request.GET.get('audience', 'all')
        if audience != 'all' and audience not in self.ROLES:
            return bad_request_response(message="Choose customers, vendors, riders or all.")
        include_unsubscribed = request.GET.get('include_unsubscribed') in ('1', 'true')

        users = User.objects.filter(is_active=True).exclude(email__isnull=True).exclude(email='')
        if audience == 'all':
            users = users.filter(role__in=list(self.ROLES.values()))
        else:
            users = users.filter(role=self.ROLES[audience])
        if not include_unsubscribed:
            users = users.filter(marketing_emails_opt_in=True)
        users = users.order_by('created_at')

        businesses = dict(Vendor.objects.filter(user__in=users).values_list('user_id', 'name'))

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        filename = f"findmytaste-{audience}-{timezone.localdate().isoformat()}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.write('\ufeff')  # BOM so Excel shows names with accents correctly
        writer = csv.writer(response)
        writer.writerow([
            'EMAIL', 'FIRSTNAME', 'LASTNAME', 'SMS', 'ROLE', 'BUSINESS_NAME',
            'SIGNED_UP', 'MARKETING_OPT_IN',
        ])
        for user in users.only(
                'id', 'email', 'full_name', 'phone_number', 'role', 'created_at',
                'marketing_emails_opt_in').iterator():
            names = (user.full_name or '').split()
            phone = normalize_nigerian_phone(user.phone_number)
            writer.writerow([
                user.email.strip().lower(),
                names[0] if names else '',
                ' '.join(names[1:]),
                f'+{phone}' if phone else '',
                self.ROLE_LABELS.get(user.role, user.role),
                businesses.get(user.id, ''),
                timezone.localtime(user.created_at).date().isoformat() if user.created_at else '',
                'yes' if user.marketing_emails_opt_in else 'no',
            ])
        return response


# ─────────────────────────────────────────────────────────────────────────────
# Rider rewards
# ─────────────────────────────────────────────────────────────────────────────

class RiderRewardProgramSerializer(serializers.ModelSerializer):
    awards_count = serializers.SerializerMethodField()
    total_paid = serializers.SerializerMethodField()
    current_period = serializers.SerializerMethodField()

    class Meta:
        model = RiderRewardProgram
        fields = [
            'id', 'name', 'description', 'target_deliveries', 'bonus_amount',
            'period', 'start_date', 'end_date', 'is_active', 'include_in_house_riders',
            'created_at', 'updated_at', 'awards_count', 'total_paid', 'current_period',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'awards_count', 'total_paid', 'current_period']

    def get_awards_count(self, obj):
        return obj.awards.count()

    def get_total_paid(self, obj):
        from django.db.models import Sum
        return str(obj.awards.aggregate(total=Sum('amount'))['total'] or 0)

    def get_current_period(self, obj):
        start, end = obj.current_window()
        return {
            'start': start.isoformat() if start else None,
            'end': end.isoformat() if end else None,
        }

    def validate_target_deliveries(self, value):
        if value < 1:
            raise serializers.ValidationError("Target must be at least 1 delivery.")
        return value

    def validate_bonus_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Bonus must be more than ₦0.")
        return value

    def validate(self, attrs):
        period = attrs.get('period', getattr(self.instance, 'period', 'weekly'))
        start = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end = attrs.get('end_date', getattr(self.instance, 'end_date', None))
        if period == 'custom':
            if not start or not end:
                raise serializers.ValidationError(
                    {'start_date': "Custom periods need a start and end date."})
            if end < start:
                raise serializers.ValidationError({'end_date': "End date must be after the start date."})
        return attrs


class AdminRiderRewardListView(generics.GenericAPIView):
    permission_classes = [page_permission('rider-rewards')]

    def get(self, request):
        return success_response(
            data=RiderRewardProgramSerializer(RiderRewardProgram.objects.all(), many=True).data)

    def post(self, request):
        serializer = RiderRewardProgramSerializer(data=request.data)
        if not serializer.is_valid():
            return bad_request_response(message=_first_error(serializer.errors), data=serializer.errors)
        program = serializer.save(created_by=request.user)
        return success_response(message="Reward saved.", data=RiderRewardProgramSerializer(program).data)


class AdminRiderRewardDetailView(generics.GenericAPIView):
    permission_classes = [page_permission('rider-rewards')]

    def put(self, request, id):
        program = RiderRewardProgram.objects.filter(id=id).first()
        if program is None:
            return bad_request_response(message="Reward not found.", status_code=404)
        serializer = RiderRewardProgramSerializer(program, data=request.data, partial=True)
        if not serializer.is_valid():
            return bad_request_response(message=_first_error(serializer.errors), data=serializer.errors)
        program = serializer.save()
        return success_response(message="Reward saved.", data=RiderRewardProgramSerializer(program).data)

    def delete(self, request, id):
        program = RiderRewardProgram.objects.filter(id=id).first()
        if program is None:
            return bad_request_response(message="Reward not found.", status_code=404)
        if program.awards.exists():
            # Keep the payout history; switch it off instead.
            program.is_active = False
            program.save(update_fields=['is_active', 'updated_at'])
            return success_response(
                message="This reward has already paid riders, so it was deactivated instead of deleted.")
        program.delete()
        return success_response(message="Reward deleted.")


class RiderRewardAwardSerializer(serializers.ModelSerializer):
    rider_name = serializers.SerializerMethodField()
    reference_code = serializers.SerializerMethodField()

    class Meta:
        model = RiderRewardAward
        fields = [
            'id', 'rider', 'rider_name', 'period_start', 'period_end',
            'deliveries_counted', 'amount', 'reference_code', 'created_at',
        ]

    def get_rider_name(self, obj):
        return obj.rider.user.full_name or obj.rider.user.email

    def get_reference_code(self, obj):
        return obj.wallet_transaction.reference_code if obj.wallet_transaction else None


class AdminRiderRewardAwardListView(generics.GenericAPIView):
    permission_classes = [page_permission('rider-rewards')]

    def get(self, request, id):
        awards = RiderRewardAward.objects.filter(program_id=id).select_related(
            'rider__user', 'wallet_transaction')
        return paginate_success_response_with_serializer(
            request, RiderRewardAwardSerializer, awards,
            page_size=int(request.GET.get('page_size', 20)),
        )


def _first_error(errors):
    if isinstance(errors, dict):
        for value in errors.values():
            return _first_error(value)
    if isinstance(errors, (list, tuple)) and errors:
        return _first_error(errors[0])
    return str(errors) if errors else "Invalid request."
