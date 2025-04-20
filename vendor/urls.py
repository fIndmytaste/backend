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
    path('register-business/', VendorRegisterBusinessView.as_view(), name='vendor_register_business'),
    path('category/', VendorCategoryView.as_view(), name='add_vendor_category'),
    path('product/', ProductsListCreateView.as_view(), name='list_add_product'),
    path('product/<uuid:product_id>/', ProductGetUpdateDeleteView.as_view(), name='edit_delete_product'),
    path('orders', VendorOrderListView.as_view(), name='order_list'),
]
