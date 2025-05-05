from django.urls import path
from .views import (
    BuyerVendorProductListView,
    FeaturedVendorsView,
    HotPickVendorsView,
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
    path('hot-picks/', HotPickVendorsView.as_view(), name='HotPickVendorsView'),
    path('featured/', FeaturedVendorsView.as_view(), name='FeaturedVendorsView'),
    path('product/', ProductsListCreateView.as_view(), name='list_add_product'),
    path('product/<uuid:product_id>/', ProductGetUpdateDeleteView.as_view(), name='edit_delete_product'),
    path('orders', VendorOrderListView.as_view(), name='order_list'),

    path('<vendor_id>/products', BuyerVendorProductListView.as_view(), name='order_list'),
]
