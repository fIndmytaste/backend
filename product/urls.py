from django.urls import path

from product.views import ProductBySystemCategoryView, ProductByVendorCategoryView, ProductDetailView, SystemCategoryListView, VendorDetailView


urlpatterns = [ 
    path('system-categories/', SystemCategoryListView.as_view(), name='system_categories'),
    path('product/system-category/<uuid:system_category_id>/', ProductBySystemCategoryView.as_view(), name='products_by_system_category'),
    path('product/<uuid:product_id>/', ProductDetailView.as_view(), name='product_detail'),
    path('vendor/<uuid:vendor_id>/', VendorDetailView.as_view(), name='vendor_detail'),
    path('product/vendor-category/<uuid:vendor_category_id>/', ProductByVendorCategoryView.as_view(), name='products_by_vendor_category'),
]
