from django.urls import path
from .views import (
    VendorCategoryView, 
    ProductView, 
)

urlpatterns = [
    # Vendor Endpoints
    path('vendor/category/', VendorCategoryView.as_view(), name='add_vendor_category'),
    path('vendor/product/', ProductView.as_view(), name='add_product'),
    path('vendor/product/<uuid:product_id>/', ProductView.as_view(), name='edit_delete_product'),
]
