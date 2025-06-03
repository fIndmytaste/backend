from django.urls import path

from admin_manager.views import (
    products as admin_product_view,
    vendor as admin_vendor_view,
    customer as admin_customer_view,
    riders as admin_riders_view,
)



urlpatterns = [ 
    # categories
    path('system-categories/', admin_product_view.AdminSystemCategoryListView.as_view(), name='admin_product_view-system_categories'),

    # overview
    path('dashboard/overview', admin_product_view.AdminDashboardOverviewAPIView.as_view(), name='dashboard-overview'),
    # products 
    path('product/system-category/<uuid:system_category_id>/', admin_product_view.AdminProductBySystemCategoryView.as_view(), name='admin_product_view-products_by_system_category'),
    path('product/<uuid:product_id>/', admin_product_view.AdminProductDetailView.as_view(), name='admin_product_view-product_detail'),
    path('product/<uuid:product_id>/ratings', admin_product_view.AdminProductRatingListView.as_view(), name='admin_product_view-product-rating-list'),

    # vendor
    path('vendors', admin_vendor_view.AdminVendorListView.as_view(), name='admin_product_view-vendor_list'),
    path('vendor/<uuid:vendor_id>/', admin_vendor_view.AdminVendorDetailView.as_view(), name='admin_product_view-vendor_detail'),
    path('vendor/<uuid:vendor_id>/products', admin_vendor_view.AdminVendorProductListView.as_view(), name='admin_product_view-vendor_products'),
    path('vendor/<uuid:vendor_id>/overview', admin_vendor_view.AdminVendorOverviewView.as_view(), name='admin_product_view-vendor_overview'),
    path('vendor/<uuid:vendor_id>/suspend', admin_vendor_view.AdminVendorSuspendView.as_view(), name='admin_product_view-vendor_suspend'),
    path('vendor/<uuid:vendor_id>/delete', admin_vendor_view.AdminVendorDeleteView.as_view(), name='admin_product_view-vendor_delete'),
    path('vendor/<uuid:vendor_id>/ratings', admin_vendor_view.AdminVendorRatingListView.as_view(), name='admin_vendor-ratings-list'),



    # orders
    path('orders', admin_product_view.AdminGetAllOrdersAPIView.as_view(), name='admin-orders-list'),
    path('orders/<uuid:id>/', admin_product_view.AdminOrderDetailAPIView.as_view(), name='admin-order-detail'),

    # riders
    path('riders', admin_riders_view.AdminRiderListView.as_view(), name='admin_riders-list'),
    path('riders/performance-metrics/', admin_riders_view.AllRidersPerformanceMetricsView.as_view(),name='all-riders-performance-metrics'),
    path('riders/<uuid:id>/', admin_riders_view.AdminRiderRetrieveDestroyView.as_view(), name='admin_riders-list'),
    path('riders/<uuid:id>/suspend', admin_riders_view.AdminRiderRetrieveDestroyView.as_view(), name='admin_rider-suspend'),
    path('riders/<uuid:id>/document', admin_riders_view.AdminRiderRetrieveDestroyView.as_view(), name='admin_rider-suspend'),
    path('riders/<uuid:id>/orders', admin_riders_view.AdminRiderOrderListView.as_view(), name='admin_rider-orders-list'),
    path('riders/<uuid:id>/ratings', admin_riders_view.AdminRiderReviewListView.as_view(), name='admin_rider-reviews-list'),
    path('riders/<uuid:id>/performance-metrics/',admin_riders_view.RiderPerformanceMetricsView.as_view(),name='rider-performance-metrics'),
    
         

    # Customer Management
    path('customers/', admin_customer_view.AdminCustomerListView.as_view(), name='admin-customer-list'),
    path('customer/<uuid:user_id>/', admin_customer_view.AdminCustomerDetailView.as_view(), name='admin-customer-detail'),
    path('customer/<uuid:user_id>/suspend/', admin_customer_view.AdminCustomerSuspendView.as_view(), name='admin-customer-suspend'),
    path('customer/<uuid:user_id>/delete/', admin_customer_view.AdminCustomerDeleteView.as_view(), name='admin-customer-delete'),
    path('customer/<uuid:user_id>/ban/', admin_customer_view.AdminCustomerBanView.as_view(), name='admin-customer-ban'),
    path('customer/<uuid:user_id>/orders/', admin_customer_view.AdminCustomerOrdersView.as_view(), name='admin-customer-orders'),


]
