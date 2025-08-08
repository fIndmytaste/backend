from django.urls import path

from product.views import ( 
    AddToFavoritesView,
    AllProductsView,
    CustomerCreateOrderMobileView,
    CustomerCreateOrderView,
    CustomerUpdateOrderView,
    DeleteProductImageView,
    GetDeliveryFeeView,
    HotPickProductsView,
    InternalProductDetailView,
    InternalProductListView,
    OrderDetailView,
    OrderListCreateView,
    ProductBySystemCategoryView, 
    ProductByVendorCategoryView, 
    ProductDetailView,
    ProductRatingCreateView,
    ProductRatingListView, 
    SystemCategoryListView,
    UserFavoriteListView,
    VendorBySystemCategoryView, 
    VendorDetailView,
    VendorRatingCreateView,
    VendorRatingListView
)


urlpatterns = [ 
    path('', InternalProductListView.as_view(), name='InternalProductListView'),
    path('system-categories/', SystemCategoryListView.as_view(), name='system_categories'),
    path('system-categories/<uuid:system_category_id>', ProductBySystemCategoryView.as_view(), name='ProductBySystemCategoryView'),
    path('system-categories/<uuid:system_category_id>/vendors', VendorBySystemCategoryView.as_view(), name='VendorBySystemCategoryView-'),
    path('hot-picks/', HotPickProductsView.as_view(), name='hot-pick-products'),
    path('internal-all-products', AllProductsView.as_view(), name='hot-pick-products'),
    path('product/<iamge_id>/delete-image', DeleteProductImageView.as_view(), name='DeleteProductImageView'),
    path('product/system-category/<uuid:system_category_id>/', ProductBySystemCategoryView.as_view(), name='products_by_system_category'),
    path('product/system-category/<uuid:system_category_id>/vendors', VendorBySystemCategoryView.as_view(), name='VendorBySystemCategoryView'),
    path('product/<uuid:product_id>/', ProductDetailView.as_view(), name='product_detail'),
    path('product/<uuid:product_id>/ratings', ProductRatingListView.as_view(), name='product-rating-list'),
    path('product/<uuid:product_id>/rating', ProductRatingCreateView.as_view(), name='product-rating-create'),
    path('vendor/<uuid:vendor_id>/', VendorDetailView.as_view(), name='vendor_detail'),
    path('vendor/<uuid:vendor_id>/ratings/', VendorRatingListView.as_view(), name='vendor-rating-list'),
    path('vendor/<uuid:vendor_id>/rating/', VendorRatingCreateView.as_view(), name='vendor-rating-create'),
    path('vendor/<uuid:vendor_id>/delivery-fee/', GetDeliveryFeeView.as_view(), name='vendor-delivery-fee'),
    path('product/vendor-category/<uuid:vendor_category_id>/', ProductByVendorCategoryView.as_view(), name='products_by_vendor_category'),

    # Order Endpoints
    path('order/', OrderListCreateView.as_view(), name='list_order'),
    path('order/create', CustomerCreateOrderView.as_view(), name='create__order'),
    path('order/create-mobile', CustomerCreateOrderMobileView.as_view(), name='create__order_mobile'),
    path('order/<uuid:order_id>/', OrderDetailView.as_view(), name='get_update_delete_order'),
    path('order/<uuid:order_id>/update', CustomerUpdateOrderView.as_view(), name='customer_update_delete_order'),


    path('user/favorites/', UserFavoriteListView.as_view(), name='user_favorites_list'),
    path('user/favorites/<uuid:product_id>/', AddToFavoritesView.as_view(), name='add_to_favorites'),


    path('<uuid:product_id>/', ProductDetailView.as_view(), name='add_to_favorites'),
    path('internal-products', InternalProductDetailView.as_view(), name='add_to_favorites'),


    
]
