from decimal import Decimal

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from account.models import Vendor
from product.models import (
    BukaItemServiceCharge,
    BukaVariantServiceCharge,
    Product,
    ProductVariant,
    ServiceChargeTier,
    SystemCategory,
)
from helpers.response.response_format import bad_request_response, success_response


# ── Serialiser helpers (inline, no extra file needed) ─────────────────────

def _tier_to_dict(tier):
    return {
        "id": str(tier.id),
        "system_category": str(tier.system_category_id),
        "system_category_name": tier.system_category.name,
        "vendor": str(tier.vendor_id) if tier.vendor_id else None,
        "vendor_name": tier.vendor.name if tier.vendor_id else None,
        "min_price": str(tier.min_price),
        "max_price": str(tier.max_price) if tier.max_price is not None else None,
        "flat_charge": str(tier.flat_charge),
        "is_active": tier.is_active,
        "created_at": tier.created_at.isoformat(),
        "updated_at": tier.updated_at.isoformat(),
    }


def _buka_charge_to_dict(charge):
    return {
        "id": str(charge.id),
        "target_type": "product",
        "vendor_id": str(charge.vendor_id or charge.product.vendor_id),
        "vendor_name": (charge.vendor.name if charge.vendor_id else charge.product.vendor.name),
        "product_id": str(charge.product_id),
        "product_name": charge.product.name,
        "variant_id": None,
        "variant_name": None,
        "base_price": str(charge.product.price),
        "customer_price": str(charge.product.get_price_with_service_charge()),
        "flat_charge": str(charge.flat_charge),
        "is_active": charge.is_active,
        "updated_at": charge.updated_at.isoformat(),
    }


def _buka_variant_charge_to_dict(charge):
    return {
        "id": str(charge.id),
        "target_type": "variant",
        "vendor_id": str(charge.vendor_id or charge.product.vendor_id),
        "vendor_name": (charge.vendor.name if charge.vendor_id else charge.product.vendor.name),
        "product_id": str(charge.product_id),
        "product_name": charge.product.name,
        "variant_id": str(charge.variant_id),
        "variant_name": charge.variant.name,
        "base_price": str(charge.variant.price),
        "customer_price": str(charge.variant.get_price_with_commission()),
        "flat_charge": str(charge.flat_charge),
        "is_active": charge.is_active,
        "updated_at": charge.updated_at.isoformat(),
    }


# ── Service Charge Tier views ─────────────────────────────────────────────

class AdminServiceChargeTierListCreateView(APIView):
    """
    GET  /admin-manager/pricing/service-charge-tiers/
         ?category_id=<uuid>   filter by system category

    POST /admin-manager/pricing/service-charge-tiers/
         Create a new tier.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = ServiceChargeTier.objects.select_related('system_category', 'vendor').order_by(
            'system_category__name', 'vendor__name', 'min_price'
        )
        cat_id = request.query_params.get('category_id')
        if cat_id:
            qs = qs.filter(system_category_id=cat_id)
        vendor_id = request.query_params.get('vendor_id')
        if vendor_id:
            qs = qs.filter(vendor_id=vendor_id)

        return success_response(
            message="Service charge tiers retrieved.",
            data=[_tier_to_dict(t) for t in qs],
        )

    def post(self, request):
        data = request.data
        required = ['system_category_id', 'min_price', 'flat_charge']
        missing = [f for f in required if not data.get(f)]
        if missing:
            return bad_request_response(message=f"Missing fields: {', '.join(missing)}")

        try:
            category = SystemCategory.objects.get(pk=data['system_category_id'])
        except SystemCategory.DoesNotExist:
            return bad_request_response(message="System category not found.")

        vendor = None
        if data.get('vendor_id'):
            try:
                vendor = Vendor.objects.get(pk=data['vendor_id'])
            except Vendor.DoesNotExist:
                return bad_request_response(message="Vendor not found.")

        tier = ServiceChargeTier.objects.create(
            system_category=category,
            vendor=vendor,
            min_price=Decimal(str(data['min_price'])),
            max_price=Decimal(str(data['max_price'])) if data.get('max_price') else None,
            flat_charge=Decimal(str(data['flat_charge'])),
            is_active=data.get('is_active', True),
        )
        return Response(
            {"status": True, "message": "Tier created.", "data": _tier_to_dict(tier)},
            status=status.HTTP_201_CREATED,
        )


class AdminServiceChargeTierDetailView(APIView):
    """
    GET    /admin-manager/pricing/service-charge-tiers/<tier_id>/
    PATCH  — update min_price, max_price, flat_charge, is_active
    DELETE — remove tier
    """
    permission_classes = [IsAuthenticated]

    def _get_tier(self, tier_id):
        try:
            return ServiceChargeTier.objects.select_related('system_category', 'vendor').get(pk=tier_id)
        except ServiceChargeTier.DoesNotExist:
            return None

    def get(self, request, tier_id):
        tier = self._get_tier(tier_id)
        if not tier:
            return bad_request_response(message="Tier not found.")
        return success_response(message="Tier retrieved.", data=_tier_to_dict(tier))

    def patch(self, request, tier_id):
        tier = self._get_tier(tier_id)
        if not tier:
            return bad_request_response(message="Tier not found.")

        data = request.data
        if 'min_price' in data:
            tier.min_price = Decimal(str(data['min_price']))
        if 'max_price' in data:
            tier.max_price = Decimal(str(data['max_price'])) if data['max_price'] else None
        if 'flat_charge' in data:
            tier.flat_charge = Decimal(str(data['flat_charge']))
        if 'is_active' in data:
            tier.is_active = bool(data['is_active'])
        tier.save()
        return success_response(message="Tier updated.", data=_tier_to_dict(tier))

    def delete(self, request, tier_id):
        tier = self._get_tier(tier_id)
        if not tier:
            return bad_request_response(message="Tier not found.")
        tier.delete()
        return success_response(message="Tier deleted.", data={})


# ── Buka per-item service charge views ───────────────────────────────────

class AdminBukaServiceChargeListView(APIView):
    """
    GET  /admin-manager/pricing/buka-service-charges/
         ?vendor_id=<uuid>   filter by vendor

    POST — set/create a service charge for a product.
         { "product_id": "...", "flat_charge": 50 }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        product_charges = BukaItemServiceCharge.objects.select_related('product', 'vendor', 'product__vendor').order_by(
            'vendor__name', 'product__name'
        )
        variant_charges = BukaVariantServiceCharge.objects.select_related(
            'product', 'vendor', 'product__vendor', 'variant', 'variant__category'
        ).order_by('vendor__name', 'product__name', 'variant__name')
        vendor_id = request.query_params.get('vendor_id')
        if vendor_id:
            product_charges = product_charges.filter(vendor_id=vendor_id)
            variant_charges = variant_charges.filter(vendor_id=vendor_id)

        data = [_buka_charge_to_dict(c) for c in product_charges]
        data.extend(_buka_variant_charge_to_dict(c) for c in variant_charges)
        data.sort(key=lambda item: (
            item["vendor_name"] or "",
            item["product_name"] or "",
            item["variant_name"] or "",
        ))
        return success_response(
            message="Buka service charges retrieved.",
            data=data,
        )

    def post(self, request):
        data = request.data
        product_id = data.get('product_id')
        variant_id = data.get('variant_id')
        flat_charge = data.get('flat_charge')

        if not product_id or flat_charge is None:
            return bad_request_response(message="product_id and flat_charge are required.")

        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            return bad_request_response(message="Product not found.")

        if variant_id:
            try:
                variant = ProductVariant.objects.select_related('product').get(
                    pk=variant_id,
                    product=product,
                )
            except ProductVariant.DoesNotExist:
                return bad_request_response(message="Variant not found for this product.")

            charge, created = BukaVariantServiceCharge.objects.update_or_create(
                variant=variant,
                defaults={
                    'vendor': product.vendor,
                    'product': product,
                    'flat_charge': Decimal(str(flat_charge)),
                    'is_active': data.get('is_active', True),
                },
            )
            return Response(
                {
                    "status": True,
                    "message": "Variant service charge saved.",
                    "data": _buka_variant_charge_to_dict(charge),
                },
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )

        charge, created = BukaItemServiceCharge.objects.update_or_create(
            product=product,
            defaults={
                'vendor': product.vendor,
                'flat_charge': Decimal(str(flat_charge)),
                'is_active': data.get('is_active', True),
            },
        )
        return Response(
            {
                "status": True,
                "message": "Service charge saved.",
                "data": _buka_charge_to_dict(charge),
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class AdminBukaVendorProductListView(APIView):
    """
    GET /admin-manager/pricing/buka-service-charges/products/?vendor_id=<uuid>
    Returns products for one vendor so the admin UI can pick vendor first,
    then product, without listing every product in the system.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        vendor_id = request.query_params.get('vendor_id')
        if not vendor_id:
            return bad_request_response(message="vendor_id is required.")

        products = (
            Product.objects
            .filter(vendor_id=vendor_id, is_delete=False)
            .order_by('name')
        )

        return success_response(
            message="Vendor products retrieved.",
            data=[
                {
                    "id": str(product.id),
                    "name": product.name,
                    "base_price": str(product.price),
                    "customer_price": str(product.get_price_with_service_charge()),
                    "has_buka_charge": hasattr(product, 'buka_service_charge'),
                    "variants": [
                        {
                            "id": str(variant.id),
                            "name": variant.name,
                            "category_name": variant.category.category_name,
                            "base_price": str(variant.price),
                            "customer_price": str(variant.get_price_with_commission()),
                            "has_buka_charge": hasattr(variant, 'buka_service_charge'),
                        }
                        for variant in ProductVariant.objects.select_related('category')
                        .filter(product=product, is_active=True)
                        .order_by('category__category_name', 'name')
                    ],
                }
                for product in products
            ],
        )


class AdminBukaServiceChargeDetailView(APIView):
    """
    GET   /admin-manager/pricing/buka-service-charges/<charge_id>/
    PATCH — update flat_charge / is_active
    DELETE
    """
    permission_classes = [IsAuthenticated]

    def _get(self, charge_id):
        try:
            return BukaItemServiceCharge.objects.select_related('product', 'vendor', 'product__vendor').get(pk=charge_id)
        except BukaItemServiceCharge.DoesNotExist:
            pass
        try:
            return BukaVariantServiceCharge.objects.select_related(
                'product', 'vendor', 'product__vendor', 'variant', 'variant__category'
            ).get(pk=charge_id)
        except BukaVariantServiceCharge.DoesNotExist:
            return None

    def _to_dict(self, charge):
        if isinstance(charge, BukaVariantServiceCharge):
            return _buka_variant_charge_to_dict(charge)
        return _buka_charge_to_dict(charge)

    def get(self, request, charge_id):
        charge = self._get(charge_id)
        if not charge:
            return bad_request_response(message="Charge not found.")
        return success_response(message="Charge retrieved.", data=self._to_dict(charge))

    def patch(self, request, charge_id):
        charge = self._get(charge_id)
        if not charge:
            return bad_request_response(message="Charge not found.")

        data = request.data
        if 'flat_charge' in data:
            charge.flat_charge = Decimal(str(data['flat_charge']))
        if 'is_active' in data:
            charge.is_active = bool(data['is_active'])
        charge.save()
        return success_response(message="Charge updated.", data=self._to_dict(charge))

    def delete(self, request, charge_id):
        charge = self._get(charge_id)
        if not charge:
            return bad_request_response(message="Charge not found.")
        charge.delete()
        return success_response(message="Charge deleted.", data={})
