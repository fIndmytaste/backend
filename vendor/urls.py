from django.urls import path
from .views import (
    ProductGetUpdateDeleteView,
    ProductsListCreateView,
    VendorCategoryView, 
)

urlpatterns = [
    # Vendor Endpoints
    path('vendor/category/', VendorCategoryView.as_view(), name='add_vendor_category'),
    path('vendor/product/', ProductsListCreateView.as_view(), name='list_add_product'),
    path('vendor/product/<uuid:product_id>/', ProductGetUpdateDeleteView.as_view(), name='edit_delete_product'),
]
