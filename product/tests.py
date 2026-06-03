from django.test import TestCase
from rest_framework.exceptions import ValidationError

from account.models import User, Vendor
from product.models import Product, ProductVariant, ProductVariantCategory, SystemCategory
from product.views import reserve_order_stock


class ReserveOrderStockTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="vendor@example.com",
            password="password",
            role="vendor",
        )
        self.stock_category = SystemCategory.objects.create(
            name="Marketplace",
            name_key="marketplace",
            description="Stock managed",
            is_stock=True,
        )
        self.food_category = SystemCategory.objects.create(
            name="Food",
            name_key="food",
            description="Not stock managed",
            is_stock=False,
        )
        self.vendor = Vendor.objects.create(
            user=self.user,
            name="Vendor",
            email="vendor@example.com",
            category=self.stock_category,
            approval_status="approved",
            is_active=True,
        )

    def test_decrements_stock_managed_product_and_purchases(self):
        product = Product.objects.create(
            name="Rice Bag",
            description="25kg",
            price=100,
            stock=5,
            vendor=self.vendor,
            system_category=self.stock_category,
        )

        reserve_order_stock({product.id: 3})

        product.refresh_from_db()
        self.assertEqual(product.stock, 2)
        self.assertEqual(product.purchases, 3)

    def test_rejects_product_quantity_above_available_stock(self):
        product = Product.objects.create(
            name="Oil",
            description="Bottle",
            price=100,
            stock=1,
            vendor=self.vendor,
            system_category=self.stock_category,
        )

        with self.assertRaises(ValidationError):
            reserve_order_stock({product.id: 2})

        product.refresh_from_db()
        self.assertEqual(product.stock, 1)
        self.assertEqual(product.purchases, 0)

    def test_ignores_non_stock_categories(self):
        product = Product.objects.create(
            name="Jollof",
            description="Plate",
            price=100,
            stock=0,
            vendor=self.vendor,
            system_category=self.food_category,
        )

        reserve_order_stock({product.id: 4})

        product.refresh_from_db()
        self.assertEqual(product.stock, 0)
        self.assertEqual(product.purchases, 0)

    def test_decrements_stock_managed_variant_options(self):
        product = Product.objects.create(
            name="Soup Bowl",
            description="With options",
            price=100,
            stock=5,
            vendor=self.vendor,
            system_category=self.stock_category,
        )
        category = ProductVariantCategory.objects.create(
            category_name="Protein",
            parent_product=product,
        )
        variant = ProductVariant.objects.create(
            category=category,
            product=product,
            name="Beef",
            price=50,
            stock=3,
            track_stock=True,
        )

        reserve_order_stock({product.id: 2}, {variant.id: 2})

        product.refresh_from_db()
        variant.refresh_from_db()
        self.assertEqual(product.stock, 3)
        self.assertEqual(product.purchases, 2)
        self.assertEqual(variant.stock, 1)

    def test_allows_untracked_stock_managed_variant_option_with_zero_stock(self):
        product = Product.objects.create(
            name="Soup Bowl",
            description="With options",
            price=100,
            stock=5,
            vendor=self.vendor,
            system_category=self.stock_category,
        )
        category = ProductVariantCategory.objects.create(
            category_name="Protein",
            parent_product=product,
        )
        variant = ProductVariant.objects.create(
            category=category,
            product=product,
            name="Beef",
            price=50,
            stock=0,
        )

        reserve_order_stock({product.id: 1}, {variant.id: 1})

        product.refresh_from_db()
        variant.refresh_from_db()
        self.assertEqual(product.stock, 4)
        self.assertEqual(product.purchases, 1)
        self.assertEqual(variant.stock, 0)

    def test_rejects_tracked_stock_managed_variant_option_without_stock(self):
        product = Product.objects.create(
            name="Soup Bowl",
            description="With options",
            price=100,
            stock=5,
            vendor=self.vendor,
            system_category=self.stock_category,
        )
        category = ProductVariantCategory.objects.create(
            category_name="Protein",
            parent_product=product,
        )
        variant = ProductVariant.objects.create(
            category=category,
            product=product,
            name="Beef",
            price=50,
            stock=0,
            track_stock=True,
        )

        with self.assertRaises(ValidationError):
            reserve_order_stock({product.id: 1}, {variant.id: 1})

        product.refresh_from_db()
        variant.refresh_from_db()
        self.assertEqual(product.stock, 5)
        self.assertEqual(product.purchases, 0)
        self.assertEqual(variant.stock, 0)

    def test_decrements_child_product_variants(self):
        parent = Product.objects.create(
            name="Rice",
            description="Parent",
            price=100,
            stock=5,
            vendor=self.vendor,
            system_category=self.stock_category,
        )
        child_variant = Product.objects.create(
            name="Large Rice",
            description="Variant",
            price=150,
            stock=3,
            vendor=self.vendor,
            system_category=self.stock_category,
            parent=parent,
        )

        reserve_order_stock({child_variant.id: 2})

        child_variant.refresh_from_db()
        self.assertEqual(child_variant.stock, 1)
        self.assertEqual(child_variant.purchases, 2)
