from django.urls import path

from admin_manager.views import products as admin_product_view


urlpatterns = [ 
    # categories
    path('system-categories/', admin_product_view.AdminSystemCategoryListView.as_view(), name='admin_product_view-system_categories'),
    # products 
    path('product/system-category/<uuid:system_category_id>/', admin_product_view.AdminProductBySystemCategoryView.as_view(), name='admin_product_view-products_by_system_category'),
    path('product/<uuid:product_id>/', admin_product_view.AdminProductDetailView.as_view(), name='admin_product_view-product_detail'),
    path('product/<uuid:product_id>/ratings', admin_product_view.AdminProductRatingListView.as_view(), name='admin_product_view-product-rating-list'),
]
