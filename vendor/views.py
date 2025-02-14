from rest_framework import status
from rest_framework import generics

from helpers.permissions import IsVendor
from product.models import Product
from .serializers import VendorCategorySerializer, ProductSerializer
from helpers.response.response_format import success_response

# Vendor Views

class VendorCategoryView(generics.GenericAPIView):
    permission_classes =[IsVendor]
    serializer_class = VendorCategorySerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(serializer.data, status_code=status.HTTP_201_CREATED)


class ProductView(generics.GenericAPIView):
    permission_classes =[IsVendor]
    serializer_class = ProductSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(serializer.data, status_code=status.HTTP_201_CREATED)

    def put(self, request, product_id):
        product = Product.objects.get(id=product_id)
        serializer = ProductSerializer(product, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(serializer.data, status_code=status.HTTP_201_CREATED)

    def delete(self, request, product_id):
        product = Product.objects.get(id=product_id)
        product.delete()
        return success_response(status_code=status.HTTP_204_NO_CONTENT)

