from rest_framework import generics

from account.models import Vendor
from vendor.serializers import ProductSerializer, SystemCategorySerializer, VendorSerializer
from .models import SystemCategory, Product
from helpers.response.response_format import success_response

# Vendor Views



# Buyer Views
class SystemCategoryListView(generics.GenericAPIView):

    serializer_class = SystemCategorySerializer

    def get(self, request):
        categories = SystemCategory.objects.all()
        serializer = self.serializer_class(categories, many=True)
        return success_response(serializer.data)


class ProductBySystemCategoryView(generics.GenericAPIView):
    """
    Endpoint to get products by system category
    """

    serializer_class = ProductSerializer

    def get(self, request, system_category_id):
        products = Product.objects.filter(system_category_id=system_category_id)
        serializer = self.serializer_class(products, many=True)
        return success_response(serializer.data)


class ProductDetailView(generics.GenericAPIView):
    serializer_class = ProductSerializer
    def get(self, request, product_id):
        product = Product.objects.get(id=product_id)
        serializer = self.serializer_class(product)
        return success_response(serializer.data)


class VendorDetailView(generics.GenericAPIView):
    serializer_class = VendorSerializer
    def get(self, request, vendor_id):
        vendor = Vendor.objects.get(id=vendor_id)
        serializer = self.serializer_class(vendor)
        return success_response(serializer.data)


class ProductByVendorCategoryView(generics.GenericAPIView):
    serializer_class = ProductSerializer
    def get(self, request, vendor_category_id):
        products = Product.objects.filter(category_id=vendor_category_id)
        serializer = self.serializer_class(products, many=True)
        return success_response(serializer.data)
