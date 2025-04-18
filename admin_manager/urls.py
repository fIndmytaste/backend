from django.urls import path

from admin_manager.views import (
    products as admin_product_view,
    vendor as admin_vendor_view,
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

    # orders
    path('orders', admin_product_view.AdminGetAllOrdersAPIView.as_view(), name='admin-orders-list'),
    path('orders/<uuid:id>/', admin_product_view.AdminOrderDetailAPIView.as_view(), name='admin-order-detail'),


]
