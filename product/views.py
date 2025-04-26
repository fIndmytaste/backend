from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from drf_yasg import openapi
from django.db.models import F

from account.models import Vendor, VendorRating
from account.serializers import VendorRatingSerializer
from product.serializers import FavoriteSerializer, OrderSerializer, RatingSerializer
from vendor.serializers import ProductSerializer, SystemCategorySerializer, VendorSerializer
from .models import Favorite, Order, Rating, SystemCategory, Product
from helpers.response.response_format import paginate_success_response_with_serializer, success_response, bad_request_response
from drf_yasg.utils import swagger_auto_schema


# Vendor Views

# Buyer Views

class SystemCategoryListView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SystemCategorySerializer

    @swagger_auto_schema(
        operation_description="Get a list of all system categories.",
        operation_summary="Retrieve a list of all system categories.",
        responses={
            200: SystemCategorySerializer(many=True),
            401: "Unauthorized",
        }
    )
    def get(self, request):
        categories = SystemCategory.objects.all()
        serializer = self.serializer_class(categories, many=True)
        return success_response(serializer.data)




class AllProductsView(generics.GenericAPIView):
    """
    Endpoint to get products by system category.
    """
    # permission_classes = [IsAuthenticated]
    serializer_class = ProductSerializer
    
    def get(self, request):
        products = Product.objects.all()
        serializer = self.serializer_class(products, many=True,context={'request': request})
        return success_response(serializer.data)



class ProductBySystemCategoryView(generics.GenericAPIView):
    """
    Endpoint to get products by system category.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ProductSerializer

    @swagger_auto_schema(
        operation_description="Get a list of products belonging to a system category.",
        operation_summary="Retrieve products by system category.",
        responses={
            200: ProductSerializer(many=True),
            400: "Bad Request",
            401: "Unauthorized",
        },
        parameters=[
            {
                'name': 'system_category_id',
                'description': 'The ID of the system category to filter products by.',
                'required': True,
                'type': 'integer',
            }
        ]
    )
    def get(self, request, system_category_id):
        products = Product.objects.filter(system_category_id=system_category_id)
        serializer = self.serializer_class(products, many=True)
        return success_response(serializer.data)


class VendorBySystemCategoryView(generics.GenericAPIView):
    """
    Endpoint to get vendors by system category.
    """
    # permission_classes = [IsAuthenticated]
    # serializer_class = ProductSerializer

    # @swagger_auto_schema(
    #     operation_description="Get a list of products belonging to a system category.",
    #     operation_summary="Retrieve products by system category.",
    #     responses={
    #         200: ProductSerializer(many=True),
    #         400: "Bad Request",
    #         401: "Unauthorized",
    #     },
    #     parameters=[
    #         {
    #             'name': 'system_category_id',
    #             'description': 'The ID of the system category to filter products by.',
    #             'required': True,
    #             'type': 'integer',
    #         }
    #     ]
    # )
    # def get(self, request, system_category_id):
    #     products = Product.objects.filter(system_category_id=system_category_id)
    #     serializer = self.serializer_class(products, many=True)
    #     return success_response(serializer.data)

    serializer_class = VendorSerializer
    permission_classes = [IsAuthenticated]
    queryset = Vendor.objects.all()

    @swagger_auto_schema(
        operation_description="Get vendors by system category",
        operation_summary="vendors by system category",
        responses={
            200: VendorSerializer,
        }
    )
    def get(self, request , system_category_id):

        queryset = Vendor.objects.filter(category__id=system_category_id)
        return paginate_success_response_with_serializer(
            request,
            self.serializer_class,
            queryset,
            page_size=int(request.GET.get('page_size',20))
        )
    
    
class HotPickProductsView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProductSerializer

    @swagger_auto_schema(
        operation_description="Get hot pick products by combining user favorites, top viewed, and highest rated products.",
        operation_summary="Retrieve hot pick products (favorites, top viewed, highest rated).",
        responses={
            200: ProductSerializer(many=True),
            400: "Bad Request",
            401: "Unauthorized",
        },
        parameters=[
            {
                'name': 'limit',
                'description': 'Limit the number of products returned (default is 10).',
                'required': False,
                'type': 'integer',
                'default': 10
            }
        ]
    )
    def get(self, request):
        limit = int(request.GET.get('limit', 10))

        # Get the user's favorited products
        favorite_products = list(self.get_user_favorites(request.user))

        # Get top viewed products
        top_viewed_products = list(self.get_top_viewed_products(limit))

        # Get highest rated products (assuming rating logic exists in your system)
        highest_rated_products = list(self.get_highest_rated_products(limit))

        # Combine products: Avoid duplicates using set()
        combined_products = set(favorite_products + top_viewed_products + highest_rated_products)

        # Get the system categories from the combined list
        system_categories = self.get_system_categories_from_products(combined_products)

        # Filter products by system categories
        filtered_products = self.get_products_by_system_categories(system_categories)

        # Limit the results to 'limit' number of products
        serializer = self.serializer_class(filtered_products[:limit], many=True)
        return paginate_success_response_with_serializer(
            request,
            self.serializer_class,
            filtered_products[:limit],
            limit
        )
        # return success_response(serializer.data)



    def get_user_favorites(self, user):
        """
        Get all the user's favorited products.
        """
        favorites = Favorite.objects.filter(user=user)
        return [favorite.product for favorite in favorites]

    def get_top_viewed_products(self, limit=10):
        """
        Get the top viewed products based on the 'views' field.
        """
        return Product.objects.order_by('-views')[:limit]

    def get_highest_rated_products(self, limit=10):
        """
        Get the highest rated products based on their rating score (assuming a Rating model exists).
        """
        # Assuming a Rating model exists and has a 'product' and 'rating' field
        return Product.objects.annotate(avg_rating=F('ratings__rating')).order_by('-avg_rating')[:limit]

    def get_system_categories_from_products(self, products):
        """
        Get the system categories associated with the products.
        """
        return set(product.system_category for product in products if product.system_category)

    def get_products_by_system_categories(self, system_categories):
        """
        Get products filtered by their system categories.
        """
        return Product.objects.filter(system_category__in=system_categories)



class ProductDetailView(generics.GenericAPIView):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get the details of a product.",
        operation_summary="Retrieve the details of a specific product.",
        responses={
            200: ProductSerializer,
            404: "Product Not Found",
            401: "Unauthorized",
        }
    )
    def get(self, request, product_id):
        product = Product.objects.get(id=product_id)
        serializer = self.serializer_class(product)
        return success_response(serializer.data)



class ProductRatingCreateView(generics.CreateAPIView):
    serializer_class = RatingSerializer
    permission_classes = [IsAuthenticated]

    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
        return success_response(
            serializer.data,
        )

    
    @swagger_auto_schema(
        operation_description="Submit a rating for a specific product.",
        operation_summary="Submit a rating for a product.",
        request_body=RatingSerializer,
        responses={
            201: openapi.Response(
                description="Product rating successfully created.",
                schema=RatingSerializer
            ),
            400: "Bad request if the rating data is invalid.",
            401: "Authentication required."
        }
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)



class ProductRatingListView(generics.ListAPIView):
    serializer_class = RatingSerializer
    permission_classes = [IsAuthenticated]

    
    def get_queryset(self):
        product_id = self.kwargs['product_id']
        try:
            product = Product.objects.get(id=product_id)
            return Rating.objects.filter(product=product)
        except Product.DoesNotExist:
            return Rating.objects.none()  
        
    @swagger_auto_schema(
        operation_description="Get all ratings for a specific product.",
        operation_summary="Retrieve ratings for a product.",
        responses={
            200: RatingSerializer(many=True),
            404: "Product not found.",
            401: "Authentication required."
        }
    )
    def get(self,request,*args,**kwargs):
        return success_response(
            data=self.serializer_class(self.get_queryset()).data
        )


class VendorDetailView(generics.GenericAPIView):
    serializer_class = VendorSerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get the details of a vendor.",
        operation_summary="Retrieve the details of a specific vendor.",
        responses={
            200: VendorSerializer,
            404: "Vendor Not Found",
            401: "Unauthorized",
        }
    )
    def get(self, request, vendor_id):
        vendor = Vendor.objects.get(id=vendor_id)
        serializer = self.serializer_class(vendor)
        return success_response(serializer.data)




class VendorRatingCreateView(generics.CreateAPIView):
    serializer_class = VendorRatingSerializer
    permission_classes = [IsAuthenticated]

    
    def perform_create(self, serializer):
        # Automatically associate the user with the rating
        serializer.save(user=self.request.user)
        return success_response(serializer.data)

    @swagger_auto_schema(
        operation_description="Submit a rating for a specific vendor.",
        operation_summary="Submit a rating for a vendor.",
        request_body=VendorRatingSerializer,
        responses={
            201: openapi.Response(
                description="Vendor rating successfully created.",
                schema=VendorRatingSerializer
            ),
            400: "Bad request if the rating data is invalid.",
            401: "Authentication required."
        }
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

class ProductByVendorCategoryView(generics.GenericAPIView):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get products by vendor category.",
        operation_summary="Retrieve products by vendor category.",
        responses={
            200: ProductSerializer(many=True),
            400: "Bad Request",
            401: "Unauthorized",
        },
        parameters=[
            {
                'name': 'vendor_category_id',
                'description': 'The ID of the vendor category to filter products by.',
                'required': True,
                'type': 'integer',
            }
        ]
    )
    def get(self, request, vendor_category_id):
        products = Product.objects.filter(category_id=vendor_category_id)
        serializer = self.serializer_class(products, many=True)
        return success_response(serializer.data)


class VendorRatingListView(generics.ListAPIView):
    serializer_class = VendorRatingSerializer
    permission_classes = [IsAuthenticated]

    
    def get_queryset(self):
        vendor_id = self.kwargs['vendor_id']
        try:
            vendor = Vendor.objects.get(id=vendor_id)
            return VendorRating.objects.filter(vendor=vendor)
        except Vendor.DoesNotExist:
            return VendorRating.objects.none()  

    @swagger_auto_schema(
        operation_description="Get all ratings for a specific vendor.",
        operation_summary="Retrieve ratings for a vendor.",
        responses={
            200: VendorRatingSerializer(many=True),
            404: "Vendor not found.",
            401: "Authentication required."
        }
    )
    def get(self,request,*args,**kwargs):
        return success_response(
            data=self.serializer_class(self.get_queryset()).data
        )
class OrderListCreateView(generics.ListCreateAPIView):
    """
    View to list and create orders.
    - Allows users to create new orders with multiple products.
    - Lists all orders for the authenticated user.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    @swagger_auto_schema(
        operation_description="List and create orders for the authenticated user.",
        operation_summary="Retrieve and create orders.",
        responses={
            200: OrderSerializer(many=True),
            201: "Order Created",
            400: "Bad Request",
            401: "Unauthorized",
        }
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    def get_queryset(self):
        """Only return orders belonging to the authenticated user."""
        return Order.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """Override perform_create to set the user for the order."""
        serializer.save(user=self.request.user)


class OrderDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    View to retrieve, update, or delete an order.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer

    @swagger_auto_schema(
        operation_description="Retrieve, update, or delete a specific order.",
        operation_summary="Retrieve, update, or delete an order.",
        responses={
            200: OrderSerializer,
            404: "Order Not Found",
            400: "Bad Request",
            401: "Unauthorized",
        }
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    def get_queryset(self):
        """Only return orders belonging to the authenticated user."""
        return Order.objects.filter(user=self.request.user)


class UserFavoriteListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FavoriteSerializer

    @swagger_auto_schema(
        operation_description="List all products in the user's favorites.",
        operation_summary="Retrieve products from the user's favorites.",
        responses={
            200: FavoriteSerializer(many=True),
            401: "Unauthorized",
        }
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    def get_queryset(self):
        return Favorite.objects.filter(user=self.request.user).order_by('-created_at')


class AddToFavoritesView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_summary="Add a product to the user's favorites.",  # Operation summary added here
        operation_description="Add a product to the user's favorites.",
        responses={
            201: FavoriteSerializer,
            400: "Bad Request",
            401: "Unauthorized",
        }
    )
    def post(self, request, product_id):
        """
        Add a product to the user's favorites.
        """
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return bad_request_response(message="Product not found.")

        # Check if the product is already in the user's favorites
        if Favorite.objects.filter(user=request.user, product=product).exists():
            return bad_request_response(message="Product is already in your favorites.")

        favorite = Favorite.objects.create(user=request.user, product=product)
        serializer = FavoriteSerializer(favorite)
        return success_response(serializer.data, status_code=201)

    @swagger_auto_schema(
        operation_summary="Remove a product from the user's favorites.",  # Operation summary added here
        operation_description="Remove a product from the user's favorites.",
        responses={
            204: "No Content",
            400: "Bad Request",
            401: "Unauthorized",
        }
    )
    def delete(self, request, product_id):
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return bad_request_response(message="Product not found.")

        existing_product = Favorite.objects.filter(user=request.user, product=product).first()

        if not existing_product:
            return bad_request_response(message="Product is not in your favorites.")

        existing_product.delete()
        return success_response(message="Product removed from your favorites.", status_code=204)
