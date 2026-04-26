from django.urls import path

from product.views import AddToFavoritesView, UserFavoriteListView, VendorIssueReportView, VendorRatingListView
from .views import (
    AllVendorsNewView,
    AllVendorsView,
    AllVendorsNewCachedView,
    BuyerVendorProductListView,
    FeaturedVendorsView,
    GetVendorDetailView,
    HotPickVendorsView,
    InternalAllVendorsNewView,
    ProductGetUpdateDeleteView,
    ProductsListCreateView,
    VendorCategoryView,
    VendorOrderDetailAPIView,
    VendorOrderListView,
    VendorOverviewView,
    VendorRatingCreateView, 
    VendorRegisterBusinessView,
    VendorOrderActionAPIView,
    VendorPendingOrderListView,
    VendorInProgressOrderListView,
    VendorDeliveredOrderListView,
    VendorThumbnailUploadView,
    VendorLogoUploadView,
    vendor_rating_stats
)

urlpatterns = [
    # Vendor Endpoints
    path('', AllVendorsView.as_view(), name='vendor_list'),
    path('all/', AllVendorsView.as_view(), name='AllVendorsNewView'),
    path('cached/', AllVendorsNewCachedView.as_view(), name='AllVendorsNewViewCached'),
    path('internal-all/', InternalAllVendorsNewView.as_view(), name='InternalAllVendorsNewView'),
    path('register-business/', VendorRegisterBusinessView.as_view(), name='vendor_register_business'),
    path('category/', VendorCategoryView.as_view(), name='add_vendor_category'),
    path('hot-picks/', HotPickVendorsView.as_view(), name='HotPickVendorsView'),
    path('featured/', FeaturedVendorsView.as_view(), name='FeaturedVendorsView'),
    path('product/', ProductsListCreateView.as_view(), name='list_add_product'),
    path('product/<uuid:product_id>/', ProductGetUpdateDeleteView.as_view(), name='edit_delete_product'),
    path('orders/', VendorOrderListView.as_view(), name='order_list'),
    path('orders/pending/', VendorPendingOrderListView.as_view(), name='order_list_pending'),
    path('orders/delivered/', VendorDeliveredOrderListView.as_view(), name='order_list_delivered'),
    path('orders/in-progress/', VendorInProgressOrderListView.as_view(), name='order_list_in_progress'),

    path('orders/<uuid:id>/', VendorOrderDetailAPIView.as_view(), name='vendor-order-detail'),
    path("orders/<uuid:order_id>/action/", VendorOrderActionAPIView.as_view(), name="vendor-order-action"),
    path('overview/', VendorOverviewView.as_view(), name='VendorOverviewView'),
    path('thumbnail-upload/', VendorThumbnailUploadView.as_view(), name='vendor-thumbnail-upload'),
    path('logo-upload/', VendorLogoUploadView.as_view(), name='vendor-logo-upload'),
    path('user/favorites/', UserFavoriteListView.as_view(), name='user_favorites_list'),
    path('user/favorites/add/', AddToFavoritesView.as_view(), name='add_to_favorites'),

    path('<vendor_id>/', GetVendorDetailView.as_view(), name='GetVendorDetailView'),
    path('<vendor_id>/products/', BuyerVendorProductListView.as_view(), name='BuyerVendorProductListView'),
    path('<uuid:vendor_id>/rate/', VendorRatingCreateView.as_view(), name='vendor-rate'),
    path('<uuid:vendor_id>/ratings/', VendorRatingListView.as_view(), name='vendor-ratings'),
    path('<uuid:vendor_id>/rating-stats/', vendor_rating_stats, name='vendor-rating-stats'),
    path('<uuid:vendor_id>/issue-report/', VendorIssueReportView.as_view(), name='vendor-issue-report'),
]
