from django.urls import path, include

from admin_manager.views import (
    products as admin_product_view,
    vendor as admin_vendor_view,
    customer as admin_customer_view,
    riders as admin_riders_view,
    transactions as transactions_view,
)
from admin_manager.views.analytics import (
    AdminUserLocationAnalyticsView,
    AdminOrderHeatmapView,
    AdminVendorCoverageGapView,
    AdminLocationSummaryView,
)
from admin_manager.views.announcements import (
    AnnouncementListView,
    AnnouncementDetailView,
    MarkAnnouncementAsViewedView,
    AdminAnnouncementListCreateView,
    AdminAnnouncementDetailView,
    admin_publish_announcement
)
from admin_manager.views.notifications import AdminBulkPushNotificationView
from admin_manager.views.product_creation_lock import (
    AdminCategoryProductLockSettingView,
    AdminVendorGrantProductCreationView,
    AdminVendorProductCreationStatusView,
    AdminVendorResetProductCreationGrantsView,
    AdminVendorToggleProductCreationLockView,
)
from admin_manager.views.staff_permissions import StaffPagePermissionsView
from admin_manager.views.service_charges import (
    AdminServiceChargeTierListCreateView,
    AdminServiceChargeTierDetailView,
    AdminBukaServiceChargeListView,
    AdminBukaServiceChargeDetailView,
    AdminBukaVendorProductListView,
    AdminDeliveryZonePricingListView,
    AdminDeliveryZonePricingDetailView,
)


urlpatterns = [ 
    
    # categories
    path('system-categories/', admin_product_view.AdminSystemCategoryListView.as_view(), name='admin_product_view-system_categories'),
    path('delivery-zones/', admin_product_view.AdminDeliveryZoneListView.as_view(), name='admin-delivery-zone-list'),

    # overview
    path('dashboard/overview/', admin_product_view.AdminDashboardOverviewAPIView.as_view(), name='dashboard-overview'),
    # products 
    path('product/system-category/<uuid:system_category_id>/', admin_product_view.AdminProductBySystemCategoryView.as_view(), name='admin_product_view-products_by_system_category'),
    path('product/<uuid:product_id>/', admin_product_view.AdminProductDetailView.as_view(), name='admin_product_view-product_detail'),
    path('product/<uuid:product_id>/ratings/', admin_product_view.AdminProductRatingListView.as_view(), name='admin_product_view-product-rating-list'),

    # marketplace settings
    path('marketplaces/', admin_vendor_view.AdminMarketPlaceListView.as_view(), name='admin-marketplace-list'),
    path('marketplaces/<uuid:marketplace_id>/', admin_vendor_view.AdminMarketPlaceDetailView.as_view(), name='admin-marketplace-detail'),

    # vendor
    path('marketplace-vendors/', admin_vendor_view.AdminMarketPlaceVendorListView.as_view(), name='admin_product_view-AdminMarketPlaceVendorListView'),
    path('marketplace-vendors/<uuid:vendor_id>/', admin_vendor_view.AdminVendorDetailView.as_view(), name='admin_product_view-AdminMarketPlaceVendorListView'),
    path('marketplace-vendors/<uuid:vendor_id>/orders/', admin_product_view.AdminGetMarketPlaceVendorOrdersAPIView.as_view(), name='admin_product_view-AdminMarketPlaceVendorListView'),
    path('marketplace-vendors/orders/all/', admin_product_view.AdminGetAllMarketPlaceVendorOrdersAPIView.as_view(), name='admin-marketplace-vendors-all-orders'),
    path('marketplace-riders/', admin_product_view.AdminGetMarketPlaceRiderListView.as_view(), name='admin_product_view-AdminGetMarketPlaceRiderListView'),
    path('vendors/', admin_vendor_view.AdminVendorListView.as_view(), name='admin_product_view-vendor_list'),
    path('vendor/<uuid:vendor_id>/', admin_vendor_view.AdminVendorDetailView.as_view(), name='admin_product_view-vendor_detail'),
    path('vendor/<uuid:vendor_id>/products/', admin_vendor_view.AdminVendorProductListView.as_view(), name='admin_product_view-vendor_products'),
    path('vendor/<uuid:vendor_id>/overview/', admin_vendor_view.AdminVendorOverviewView.as_view(), name='admin_product_view-vendor_overview'),
    path('vendor/<uuid:vendor_id>/suspend/', admin_vendor_view.AdminVendorSuspendView.as_view(), name='admin_product_view-vendor_suspend'),
    path('vendor/<uuid:vendor_id>/delete/', admin_vendor_view.AdminVendorDeleteView.as_view(), name='admin_product_view-vendor_delete'),
    path('vendor/<uuid:vendor_id>/ratings/', admin_vendor_view.AdminVendorRatingListView.as_view(), name='admin_vendor-ratings-list'),

    # product creation lock (per-vendor)
    path('vendor/<uuid:vendor_id>/product-creation/', AdminVendorProductCreationStatusView.as_view(), name='admin-vendor-product-creation-status'),
    path('vendor/<uuid:vendor_id>/grant-product-creation/', AdminVendorGrantProductCreationView.as_view(), name='admin-vendor-grant-product-creation'),
    path('vendor/<uuid:vendor_id>/reset-product-creation-grants/', AdminVendorResetProductCreationGrantsView.as_view(), name='admin-vendor-reset-product-creation-grants'),
    path('vendor/<uuid:vendor_id>/product-creation-lock/', AdminVendorToggleProductCreationLockView.as_view(), name='admin-vendor-product-creation-lock'),

    # product creation lock (per-category)
    path('system-categories/<uuid:category_id>/product-lock/', AdminCategoryProductLockSettingView.as_view(), name='admin-category-product-lock'),

    # orders
    path('orders/', admin_product_view.AdminGetAllOrdersAPIView.as_view(), name='admin-orders-list'),
    path('promo-orders/', admin_product_view.AdminPromoOrdersAPIView.as_view(), name='admin-promo-orders-list'),
    path('orders/<uuid:id>/', admin_product_view.AdminOrderDetailAPIView.as_view(), name='admin-order-detail'),
    path('orders/<uuid:id>/parties/', admin_product_view.AdminOrderDetailVendorRiderAPIView.as_view(), name='admin-users-detail'),
    path('orders/<uuid:id>/confirm-pickup/', admin_product_view.AdminMarketplaceConfirmPickupAPIView.as_view(), name='admin-marketplace-confirm-pickup'),

    # riders
    path('riders/', admin_riders_view.AdminRiderListView.as_view(), name='admin_riders-list'),
    path('riders/performance-metrics/', admin_riders_view.AllRidersPerformanceMetricsView.as_view(),name='all-riders-performance-metrics'),
    path('riders/<uuid:id>/', admin_riders_view.AdminRiderRetrieveDestroyView.as_view(), name='admin_riders-list'),
    path('riders/<uuid:id>/suspend/', admin_riders_view.AdminRiderRetrieveDestroyView.as_view(), name='admin_rider-suspend'),
    path('riders/<uuid:id>/document-status/', admin_riders_view.AdminRiderDocumentverificationView.as_view(), name='admin_rider-document-status'),
    path('riders/<uuid:id>/document/', admin_riders_view.AdminRiderRetrieveDestroyView.as_view(), name='admin_rider-document'),
    path('riders/<uuid:id>/orders/', admin_riders_view.AdminRiderOrderListView.as_view(), name='admin_rider-orders-list'),
    path('riders/<uuid:id>/ratings/', admin_riders_view.AdminRiderReviewListView.as_view(), name='admin_rider-reviews-list'),
    path('riders/<uuid:id>/performance-metrics/',admin_riders_view.RiderPerformanceMetricsView.as_view(),name='rider-performance-metrics'),
    path('riders/<uuid:id>/earning-metrics/',admin_riders_view.RiderEarningMetricsView.as_view(),name='rider-earning-metrics'),

    # Assign order to rider
    path('riders/<uuid:id>/assign-order/', admin_riders_view.AdminAssignOrderToRiderView.as_view(), name='admin_assign_order_to_rider'),
    path('marketplace-orders/bulk-assign-rider/', admin_riders_view.AdminBulkAssignMarketplaceOrdersView.as_view(), name='admin_bulk_assign_marketplace_orders'),
    
         

    # Customer Management
    path('customers/', admin_customer_view.AdminCustomerListView.as_view(), name='admin-customer-list'),
    path('customer/<uuid:user_id>/', admin_customer_view.AdminCustomerDetailView.as_view(), name='admin-customer-detail'),
    path('customer/<uuid:user_id>/suspend/', admin_customer_view.AdminCustomerSuspendView.as_view(), name='admin-customer-suspend'),
    path('customer/<uuid:user_id>/delete/', admin_customer_view.AdminCustomerDeleteView.as_view(), name='admin-customer-delete'),
    path('customer/<uuid:user_id>/ban/', admin_customer_view.AdminCustomerBanView.as_view(), name='admin-customer-ban'),
    path('customer/<uuid:user_id>/orders/', admin_customer_view.AdminCustomerOrdersView.as_view(), name='admin-customer-orders'),
    path('customer/<uuid:user_id>/orders/overview/', admin_customer_view.AdminCustomerOrdersOverviewView.as_view(), name='admin-customer-orders-overview'),



    path('transactions/', transactions_view.AdminGetTransactionsListView.as_view(), name='transactions_list'),
    path('transactions/<uuid:transaction_id>/', transactions_view.AdminGetTransactionDetailView.as_view(), name='transactions_detail'),


    path('announcements/', AnnouncementListView.as_view(), name='announcement-list'),
    path('announcements/<uuid:id>/', AnnouncementDetailView.as_view(), name='announcement-detail'),
    path('announcements/mark-viewed/', MarkAnnouncementAsViewedView.as_view(), name='announcement-mark-viewed'),
    
    # Admin endpoints
    path('admin/announcements/', AdminAnnouncementListCreateView.as_view(), name='admin-announcement-list-create'),
    path('admin/announcements/<uuid:id>/', AdminAnnouncementDetailView.as_view(), name='admin-announcement-detail'),
    path('admin/announcements/<uuid:announcement_id>/publish/', admin_publish_announcement, name='admin-announcement-publish'),


    # ── Location & Demand Analytics ────────────────────────────────────────
    # GET /admin-manager/analytics/summary/           → dashboard summary cards
    # GET /admin-manager/analytics/user-locations/   → user registration heatmap
    # GET /admin-manager/analytics/order-heatmap/    → order demand heatmap
    # GET /admin-manager/analytics/vendor-coverage-gaps/ → gap analysis
    path('analytics/summary/', AdminLocationSummaryView.as_view(), name='analytics-summary'),
    path('analytics/user-locations/', AdminUserLocationAnalyticsView.as_view(), name='analytics-user-locations'),
    path('analytics/order-heatmap/', AdminOrderHeatmapView.as_view(), name='analytics-order-heatmap'),
    path('analytics/vendor-coverage-gaps/', AdminVendorCoverageGapView.as_view(), name='analytics-vendor-coverage-gaps'),

    # Notifications
    path('notifications/bulk-push/', AdminBulkPushNotificationView.as_view(), name='admin-bulk-push'),

    # Staff page permissions — used by the custom admin frontend
    path('staff/my-pages/', StaffPagePermissionsView.as_view(), name='staff-my-pages'),

    # ── Pricing / Service Charges ──────────────────────────────────────────
    # GET  ?category_id=<uuid>  → filter tiers by category
    # POST → create tier
    path('pricing/service-charge-tiers/', AdminServiceChargeTierListCreateView.as_view(), name='admin-service-charge-tier-list'),
    path('pricing/service-charge-tiers/<uuid:tier_id>/', AdminServiceChargeTierDetailView.as_view(), name='admin-service-charge-tier-detail'),

    # Delivery zone item pricing
    path('pricing/delivery-zones/', AdminDeliveryZonePricingListView.as_view(), name='admin-delivery-zone-pricing-list'),
    path('pricing/delivery-zones/<uuid:zone_id>/', AdminDeliveryZonePricingDetailView.as_view(), name='admin-delivery-zone-pricing-detail'),

    # Buka per-item charges
    # GET  ?vendor_id=<uuid>  → filter by vendor
    # POST → create/update charge for a product
    path('pricing/buka-service-charges/', AdminBukaServiceChargeListView.as_view(), name='admin-buka-service-charge-list'),
    path('pricing/buka-service-charges/products/', AdminBukaVendorProductListView.as_view(), name='admin-buka-service-charge-products'),
    path('pricing/buka-service-charges/<uuid:charge_id>/', AdminBukaServiceChargeDetailView.as_view(), name='admin-buka-service-charge-detail'),
]
