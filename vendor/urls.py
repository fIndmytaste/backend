from django.urls import path

from product.views import VendorRatingListView
from .views import (
    AllVendorsView,
    BuyerVendorProductListView,
    FeaturedVendorsView,
    HotPickVendorsView,
    ProductGetUpdateDeleteView,
    ProductsListCreateView,
    VendorCategoryView,
    VendorOrderListView,
    VendorRatingCreateView, 
    VendorRegisterBusinessView,
    vendor_rating_stats
)

urlpatterns = [
    # Vendor Endpoints
    path('', AllVendorsView.as_view(), name='vendor_register_business'),
    path('register-business/', VendorRegisterBusinessView.as_view(), name='vendor_register_business'),
    path('category/', VendorCategoryView.as_view(), name='add_vendor_category'),
    path('hot-picks/', HotPickVendorsView.as_view(), name='HotPickVendorsView'),
    path('featured/', FeaturedVendorsView.as_view(), name='FeaturedVendorsView'),
    path('product/', ProductsListCreateView.as_view(), name='list_add_product'),
    path('product/<uuid:product_id>/', ProductGetUpdateDeleteView.as_view(), name='edit_delete_product'),
    path('orders', VendorOrderListView.as_view(), name='order_list'),

    path('<vendor_id>/products', BuyerVendorProductListView.as_view(), name='order_list'),
    path('vendors/<uuid:vendor_id>/rate/', VendorRatingCreateView.as_view(), name='vendor-rate'),
    path('vendors/<uuid:vendor_id>/ratings/', VendorRatingListView.as_view(), name='vendor-ratings'),
    path('vendors/<uuid:vendor_id>/rating-stats/', vendor_rating_stats, name='vendor-rating-stats'),
]
