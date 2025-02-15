from django.urls import path
from .views import (
    ProductGetUpdateDeleteView,
    ProductsListCreateView,
    VendorCategoryView,
    VendorOrderListView, 
    VendorRegisterBusinessView
)

urlpatterns = [
    # Vendor Endpoints
    path('vendor/register-business/', VendorRegisterBusinessView.as_view(), name='vendor_register_business'),
    path('vendor/category/', VendorCategoryView.as_view(), name='add_vendor_category'),
    path('vendor/product/', ProductsListCreateView.as_view(), name='list_add_product'),
    path('vendor/product/<uuid:product_id>/', ProductGetUpdateDeleteView.as_view(), name='edit_delete_product'),
    path('vendor/orders', VendorOrderListView.as_view(), name='order_list'),
]
