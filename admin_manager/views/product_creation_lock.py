"""
Admin endpoints for managing the per-vendor product-creation lock.

Flow:
  1. Vendor signs up, gets approved, uploads initial products.
  2. Admin configures pricing (BukaItemServiceCharge) on the products.
     The signal in vendor/signals.py flips vendor.product_creation_locked
     to True if the vendor's category has lock_products_after_approval.
  3. From now on, the vendor cannot create new products. If they need to
     add one, they contact support; support/admin issues a grant here.
  4. Each successful product creation decrements grant_count by 1.

This module also exposes a category-level toggle so admins can decide
which system categories participate in the lock.
"""

from rest_framework import generics, status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from django.db import transaction
from django.db.models import F

from account.models import ProductCreationGrant, Vendor
from product.models import SystemCategory
from helpers.response.response_format import (
    bad_request_response,
    success_response,
)


def _serialize_vendor_lock(vendor: Vendor) -> dict:
    category = vendor.category
    return {
        'vendor_id': str(vendor.id),
        'vendor_name': vendor.name,
        'product_creation_locked': vendor.product_creation_locked,
        'product_creation_grant_count': vendor.product_creation_grant_count,
        'category_id': str(category.id) if category else None,
        'category_name': category.name if category else None,
        'category_locks_after_approval': bool(
            category and category.lock_products_after_approval
        ),
    }


def _serialize_grant(grant: ProductCreationGrant) -> dict:
    return {
        'id': str(grant.id),
        'action': grant.action,
        'count': grant.count,
        'balance_after': grant.balance_after,
        'note': grant.note,
        'granted_by': (
            grant.granted_by.email if grant.granted_by_id else None
        ),
        'created_at': grant.created_at.isoformat(),
    }


class AdminVendorProductCreationStatusView(generics.GenericAPIView):
    """GET /admin-manager/vendor/<vendor_id>/product-creation/

    Returns the vendor's current lock state and the most recent grants."""

    permission_classes = [IsAuthenticated]

    def get(self, request, vendor_id):
        try:
            vendor = Vendor.objects.select_related('category').get(id=vendor_id)
        except Vendor.DoesNotExist:
            return bad_request_response(
                message='Vendor not found',
                status_code=status.HTTP_404_NOT_FOUND,
            )

        recent_grants = (
            ProductCreationGrant.objects
            .filter(vendor=vendor)
            .select_related('granted_by')[:20]
        )

        data = _serialize_vendor_lock(vendor)
        data['recent_actions'] = [_serialize_grant(g) for g in recent_grants]
        return success_response(data)


class AdminVendorGrantProductCreationView(generics.GenericAPIView):
    """POST /admin-manager/vendor/<vendor_id>/grant-product-creation/

    Body: { "count": <positive int>, "note": "<optional reason>" }

    Increments the vendor's grant_count by <count>. Logged in
    ProductCreationGrant for audit."""

    permission_classes = [IsAuthenticated]

    def post(self, request, vendor_id):
        try:
            vendor = Vendor.objects.get(id=vendor_id)
        except Vendor.DoesNotExist:
            return bad_request_response(
                message='Vendor not found',
                status_code=status.HTTP_404_NOT_FOUND,
            )

        raw_count = request.data.get('count')
        try:
            count = int(raw_count)
        except (TypeError, ValueError):
            return bad_request_response(
                message='count must be a positive integer'
            )
        if count <= 0:
            return bad_request_response(
                message='count must be a positive integer'
            )

        note = (request.data.get('note') or '').strip()

        with transaction.atomic():
            Vendor.objects.filter(pk=vendor.pk).update(
                product_creation_grant_count=F('product_creation_grant_count') + count
            )
            vendor.refresh_from_db(fields=['product_creation_grant_count'])
            ProductCreationGrant.objects.create(
                vendor=vendor,
                action='grant',
                count=count,
                balance_after=vendor.product_creation_grant_count,
                granted_by=request.user if request.user.is_authenticated else None,
                note=note,
            )

        return success_response(
            _serialize_vendor_lock(vendor),
            message=f'Granted {count} product creation(s).',
        )


class AdminVendorResetProductCreationGrantsView(generics.GenericAPIView):
    """POST /admin-manager/vendor/<vendor_id>/reset-product-creation-grants/

    Sets the vendor's grant_count back to 0. Used to revoke any remaining
    unused grants."""

    permission_classes = [IsAuthenticated]

    def post(self, request, vendor_id):
        try:
            vendor = Vendor.objects.get(id=vendor_id)
        except Vendor.DoesNotExist:
            return bad_request_response(
                message='Vendor not found',
                status_code=status.HTTP_404_NOT_FOUND,
            )

        note = (request.data.get('note') or '').strip()

        with transaction.atomic():
            Vendor.objects.filter(pk=vendor.pk).update(
                product_creation_grant_count=0
            )
            vendor.product_creation_grant_count = 0
            ProductCreationGrant.objects.create(
                vendor=vendor,
                action='reset',
                count=0,
                balance_after=0,
                granted_by=request.user if request.user.is_authenticated else None,
                note=note,
            )

        return success_response(
            _serialize_vendor_lock(vendor),
            message='Reset remaining product-creation grants to zero.',
        )


class AdminVendorToggleProductCreationLockView(generics.GenericAPIView):
    """PATCH /admin-manager/vendor/<vendor_id>/product-creation-lock/

    Body: { "locked": <bool>, "note": "<optional reason>" }

    Manually lock or unlock the vendor. Use carefully — the lock is
    normally driven by the auto-lock signal."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, vendor_id):
        try:
            vendor = Vendor.objects.get(id=vendor_id)
        except Vendor.DoesNotExist:
            return bad_request_response(
                message='Vendor not found',
                status_code=status.HTTP_404_NOT_FOUND,
            )

        if 'locked' not in request.data:
            return bad_request_response(message='locked field is required')

        locked = bool(request.data.get('locked'))
        note = (request.data.get('note') or '').strip()

        with transaction.atomic():
            Vendor.objects.filter(pk=vendor.pk).update(
                product_creation_locked=locked
            )
            vendor.product_creation_locked = locked
            ProductCreationGrant.objects.create(
                vendor=vendor,
                action='lock' if locked else 'unlock',
                count=0,
                balance_after=vendor.product_creation_grant_count,
                granted_by=request.user if request.user.is_authenticated else None,
                note=note,
            )

        return success_response(
            _serialize_vendor_lock(vendor),
            message=(
                'Vendor product creation locked.'
                if locked else 'Vendor product creation unlocked.'
            ),
        )


class AdminCategoryProductLockSettingView(generics.GenericAPIView):
    """PATCH /admin-manager/system-categories/<category_id>/product-lock/

    Body: { "lock_products_after_approval": <bool> }

    Turns the category-wide auto-lock policy on or off. Affects every
    vendor in this category from the next time admin pricing is set."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, category_id):
        try:
            category = SystemCategory.objects.get(id=category_id)
        except SystemCategory.DoesNotExist:
            return bad_request_response(
                message='Category not found',
                status_code=status.HTTP_404_NOT_FOUND,
            )

        if 'lock_products_after_approval' not in request.data:
            return bad_request_response(
                message='lock_products_after_approval field is required'
            )

        flag = bool(request.data.get('lock_products_after_approval'))
        SystemCategory.objects.filter(pk=category.pk).update(
            lock_products_after_approval=flag
        )
        category.lock_products_after_approval = flag

        return success_response({
            'category_id': str(category.id),
            'category_name': category.name,
            'lock_products_after_approval': category.lock_products_after_approval,
        }, message='Category product-lock policy updated.')
