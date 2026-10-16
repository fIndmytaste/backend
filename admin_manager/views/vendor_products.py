"""
Admin endpoints for managing a vendor's catalogue on their behalf.

Admins create, edit and delete products (with images, variants and
categories) for any vendor account, through the same ProductSerializer and
image pipeline the vendor app uses, so a product made here is
indistinguishable from one the vendor made themselves.

Admin writes bypass the per-vendor product-creation lock and never consume a
grant: the lock exists to make vendors go through support, and admins are
support.

Routes (all under /admin-manager/):
  GET  POST          vendor/<vendor_id>/categories/
  POST               vendor/<vendor_id>/products/create/
  GET  PATCH DELETE  vendor/<vendor_id>/products/<product_id>/
  DELETE             vendor/<vendor_id>/products/<product_id>/images/<image_id>/
"""

import logging

from django.db import transaction
from rest_framework import generics, status
from rest_framework.permissions import BasePermission, IsAuthenticated

from account.models import StaffPagePermission, Vendor
from helpers.response.response_format import bad_request_response, success_response
from product.models import Product, ProductImage, SystemCategory, VendorCategory
from vendor.serializers import ProductSerializer, VendorCategorySerializer
from vendor.views import _request_product_images, _upload_product_images_or_raise


class CanManageVendorCatalogue(BasePermission):
    """Superusers and admins, or staff granted the Vendor Management page."""

    message = "You do not have permission to manage vendor products."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_superuser or getattr(user, 'role', None) == 'admin':
            return True
        return bool(user.is_staff) and StaffPagePermission.objects.filter(
            user=user, page='vendor',
        ).exists()


def _get_vendor_or_error(vendor_id):
    vendor = Vendor.objects.select_related('category').filter(id=vendor_id).first()
    if vendor is None:
        return None, bad_request_response(
            message="Vendor not found.", status_code=status.HTTP_404_NOT_FOUND,
        )
    return vendor, None


def _get_product_or_error(vendor, product_id):
    product = Product.objects.filter(id=product_id, vendor=vendor, parent=None).first()
    if product is None:
        return None, bad_request_response(
            message="Product not found.", status_code=status.HTTP_404_NOT_FOUND,
        )
    return product, None


def _validate_categories(request, vendor):
    """Reject a menu category from another vendor or an unknown system category.

    ProductSerializer accepts any VendorCategory id, which would let a product
    show up under a different store's menu section.
    """
    category_id = request.data.get('category')
    if category_id and not VendorCategory.objects.filter(id=category_id, vendor=vendor).exists():
        return bad_request_response(message="That menu category does not belong to this vendor.")

    system_category_id = request.data.get('system_category')
    if system_category_id and not SystemCategory.objects.filter(id=system_category_id).exists():
        return bad_request_response(message="Unknown system category.")
    return None


def _serialize_product(product, request):
    product.refresh_from_db()
    return ProductSerializer(product, context={'request': request, 'is_vendor': True}).data


def _save_product(serializer, request):
    """Save the product and upload its images atomically; returns (product, error)."""
    try:
        with transaction.atomic():
            product = serializer.save()
            _upload_product_images_or_raise(product, _request_product_images(request))
    except Exception as e:
        logging.error("Admin product save failed: %s", str(e))
        return None, bad_request_response(message=f"Product image upload failed: {str(e)}")
    return product, None


class AdminVendorCategoryListCreateView(generics.GenericAPIView):
    """List a vendor's menu categories, or create one for them."""

    permission_classes = [IsAuthenticated, CanManageVendorCatalogue]
    serializer_class = VendorCategorySerializer

    def get(self, request, vendor_id):
        vendor, error = _get_vendor_or_error(vendor_id)
        if error:
            return error
        categories = VendorCategory.objects.filter(vendor=vendor, is_active=True).order_by('name')
        return success_response(self.serializer_class(categories, many=True).data)

    def post(self, request, vendor_id):
        vendor, error = _get_vendor_or_error(vendor_id)
        if error:
            return error
        name = (request.data.get('name') or '').strip()
        if not name:
            return bad_request_response(message="Category name is required.")
        existing = VendorCategory.objects.filter(vendor=vendor, name__iexact=name).first()
        if existing:
            return success_response(self.serializer_class(existing).data)
        category = VendorCategory.objects.create(
            vendor=vendor,
            name=name,
            description=(request.data.get('description') or '').strip(),
        )
        return success_response(
            self.serializer_class(category).data, status_code=status.HTTP_201_CREATED,
        )


class AdminVendorProductCreateView(generics.GenericAPIView):
    """Create a product for a vendor. Same multipart payload as the vendor app:
    name, description, price, stock, is_active, system_category, category,
    images[] and product_variant (JSON list of variant groups)."""

    permission_classes = [IsAuthenticated, CanManageVendorCatalogue]
    serializer_class = ProductSerializer

    def post(self, request, vendor_id):
        vendor, error = _get_vendor_or_error(vendor_id)
        if error:
            return error
        error = _validate_categories(request, vendor)
        if error:
            return error

        serializer = self.serializer_class(
            data=request.data,
            context={'request': request, 'is_vendor': True, 'vendor': vendor},
        )
        serializer.is_valid(raise_exception=True)
        product, error = _save_product(serializer, request)
        if error:
            return error
        return success_response(
            _serialize_product(product, request), status_code=status.HTTP_201_CREATED,
        )


class AdminVendorProductDetailView(generics.GenericAPIView):
    """Retrieve, edit or delete one of a vendor's products."""

    permission_classes = [IsAuthenticated, CanManageVendorCatalogue]
    serializer_class = ProductSerializer

    def get(self, request, vendor_id, product_id):
        vendor, error = _get_vendor_or_error(vendor_id)
        if error:
            return error
        product, error = _get_product_or_error(vendor, product_id)
        if error:
            return error
        return success_response(_serialize_product(product, request))

    def patch(self, request, vendor_id, product_id):
        vendor, error = _get_vendor_or_error(vendor_id)
        if error:
            return error
        product, error = _get_product_or_error(vendor, product_id)
        if error:
            return error
        error = _validate_categories(request, vendor)
        if error:
            return error

        serializer = self.serializer_class(
            product,
            data=request.data,
            partial=True,
            context={'request': request, 'is_vendor': True, 'vendor': vendor},
        )
        serializer.is_valid(raise_exception=True)
        product, error = _save_product(serializer, request)
        if error:
            return error
        return success_response(_serialize_product(product, request))

    def delete(self, request, vendor_id, product_id):
        vendor, error = _get_vendor_or_error(vendor_id)
        if error:
            return error
        product, error = _get_product_or_error(vendor, product_id)
        if error:
            return error
        product.delete()
        return success_response(message="Product deleted.")


class AdminVendorProductImageDeleteView(generics.GenericAPIView):
    """Remove one image from a vendor's product, promoting another to primary."""

    permission_classes = [IsAuthenticated, CanManageVendorCatalogue]

    def delete(self, request, vendor_id, product_id, image_id):
        vendor, error = _get_vendor_or_error(vendor_id)
        if error:
            return error
        product, error = _get_product_or_error(vendor, product_id)
        if error:
            return error
        image = ProductImage.objects.filter(id=image_id, product=product).first()
        if image is None:
            return bad_request_response(
                message="Image not found.", status_code=status.HTTP_404_NOT_FOUND,
            )
        was_primary = image.is_primary
        image.delete()
        if was_primary:
            replacement = ProductImage.objects.filter(product=product, is_active=True).first()
            if replacement:
                replacement.is_primary = True
                replacement.save(update_fields=['is_primary'])
        return success_response(message="Image deleted.")
