import redis
from django.conf import settings
from rest_framework import status, generics 
from django.db.models import Q, Avg,Sum, Count
from account.models import Address, Notification, Rider, User, Vendor, VendorRating
from account.serializers import VendorRatingSerializer
from helpers.order_utils import get_distance_between_two_location
from helpers.vendor_discovery import (
    approved_vendor_queryset,
    apply_vendor_search,
    filter_and_sort_vendors_by_distance,
    nearest_first_vendors,
    resolve_request_coordinates,
)
from helpers.push_notification import notification_helper
from helpers.websocket_notification import send_order_accepted_notification_customer
from helpers.permissions import IsVendor
from concurrent.futures import ThreadPoolExecutor, as_completed
from rest_framework.permissions import IsAuthenticated, AllowAny
from product.models import Order, Product, ProductImage, SystemCategory, VendorCategory, UserFavoriteVendor
from product.serializers import OrderSerializer
from vendor.models import MarketPlace
from wallet.models import Wallet, WalletTransaction
from .serializers import (
    MarketPlaceSerializer, 
    VendorCategorySerializer, 
    BuyerVendorProductSerializer,
    ProductSerializer, 
    VendorRatingCreateSerializer,
    VendorRegisterBusinessSerializer, 
    VendorSerializer,
    VendorOrderActionSerializer,
    VendorImageUploadSerializer
)
from helpers.response.response_format import internal_server_error_response, success_response, bad_request_response,paginate_success_response_with_serializer, validation_error_response
from helpers.backblaze import upload_to_backblaze
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi 
from datetime import timedelta
from rest_framework.decorators import api_view
from math import radians, cos
import logging
# Vendor Views


class VendorRegisterBusinessView(generics.GenericAPIView):
    """
    View to handle vendor categories.
    - Vendors can retrieve their own categories or create new ones.
    """
    permission_classes = [IsVendor]
    serializer_class = VendorRegisterBusinessSerializer

    @swagger_auto_schema(
        operation_summary="Register a new vendor business.",
        operation_description="Create a new vendor business with details such as name, category, and contact info.",
        responses={200: VendorRegisterBusinessSerializer()}
    )
    def post(self, request):
        print(request.headers)
        print(request.data)
        print(request.data)
        print(request.data)
        serializer  = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        name = serializer.validated_data['name']
        category = serializer.validated_data['category']
        description = serializer.validated_data['description']
        email = serializer.validated_data['email']
        phone_number = serializer.validated_data['phone_number']
        open_time = serializer.validated_data['open_time']
        close_time = serializer.validated_data['close_time']
        open_day = serializer.validated_data['open_day']
        close_day = serializer.validated_data['close_day']

        # validate the categoru
        try:
            category_obj = SystemCategory.objects.get(id=category)
        except SystemCategory.DoesNotExist:
            return bad_request_response(
                message="Invalid category"
            )
        
        marketplace = None
        if category_obj.name.lower().strip() == 'marketplace':
            # get the market place id 
            marketplace_id = request.data.get('marketplace_id')
            if not marketplace_id:
                return bad_request_response(
                    message=f" marketplace_id is required"
                )
            
            try:
                marketplace = MarketPlace.objects.get(id=marketplace_id)
            except:
                return bad_request_response(
                    message="Invalid marketplace"
                )
            
            
            

        
        user = request.user
        
        vendor_exist, _ = Vendor.objects.get_or_create(user=user)
        vendor_exist.name = name
        vendor_exist.category=category_obj
        vendor_exist.description=description
        vendor_exist.email=email
        vendor_exist.phone_number=phone_number
        vendor_exist.open_day=open_day
        vendor_exist.close_day=close_day
        vendor_exist.open_time=open_time
        vendor_exist.close_time=close_time
        vendor_exist.save()

        if marketplace:
            marketplace.vendors.add(vendor_exist)
            

        # vendor_exist = Vendor.objects.filter(email=email).first()
        # if vendor_exist:
        #     return bad_request_response(
        #         message="Vendor already exist"
        #         )
        
        # new_vendor = Vendor.objects.create(
        #     name=name,
        #     user=user,
        #     category=category_obj,
        #     description=description,
        #     email=email,
        #     phone_number=phone_number,
        #     open_day=open_day,
        #     close_day=close_day,
        #     open_time=open_time,
        #     close_time=close_time
        # )


        return success_response(
            message="Vendor created successfully",
        )
    

class VendorCategoryView(generics.GenericAPIView):
    """
    View to handle vendor categories.
    - Vendors can retrieve their own categories or create new ones.
    """
    permission_classes = [IsVendor]
    serializer_class = VendorCategorySerializer

    @swagger_auto_schema(
        operation_summary="Retrieve a list of vendor categories.",
        operation_description="Retrieve a list of vendor categories with optional search functionality.",
        responses={200: VendorCategorySerializer(many=True)}
    )
    def get(self, request):
        """
        Retrieve a list of vendor categories with optional search functionality.

        Query Parameters:
        - search (str): Search term to filter categories by name or description.

        Returns:
        - A list of vendor categories matching the search query (if provided).
        """
        search_query = request.GET.get('search', None)

        # Filter by vendor (only the vendor's categories)
        query_filter = Q(vendor=request.user)

        if search_query:
            # Add search filter for name and description
            query_filter &= (Q(name__icontains=search_query) | Q(description__icontains=search_query))
        
        # Get the categories filtered by the search query
        categories = VendorCategory.objects.filter(query_filter).order_by('-created_at')

        # Serialize and return the response
        serializer = self.serializer_class(categories, many=True)
        return success_response(serializer.data)

    @swagger_auto_schema(
        operation_summary="Create a new vendor category.",
        operation_description="Create a new vendor category with details such as name and description.",
        request_body=VendorCategorySerializer,
        responses={201: VendorCategorySerializer}
    )
    def post(self, request):
        """
        Create a new vendor category.

        Body Parameters:
        - name (str): The name of the category.
        - description (str): The description of the category.

        Returns:
        - The newly created vendor category.
        """
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(serializer.data, status_code=status.HTTP_201_CREATED)



class ProductsListCreateView(generics.GenericAPIView):
    """
    View to list and create products for a vendor.
    - Vendors can retrieve a list of their products with filters.
    - Vendors can also create new products.
    """
    permission_classes = [IsAuthenticated]  
    serializer_class = ProductSerializer

    @swagger_auto_schema(
        operation_summary="Retrieve a list of products for the vendor.",
        operation_description="Retrieve a list of products for the vendor with optional search, category, and price filters.",
        responses={200: ProductSerializer(many=True)}
    )
    def get(self, request):
        """
        Retrieve a list of products for a vendor with optional search and filters.

        Query Parameters:
        - search (str): Search term to filter products by name or description.
        - category (str): Filter products by category ID.
        - min_price (float): Filter products by minimum price.
        - max_price (float): Filter products by maximum price.
        - is_active (bool): Filter products by their active status (true/false).
        - is_featured (bool): Filter products by their featured status (true/false).

        Returns:
        - A list of products matching the provided filters.
        """
        vendor = Vendor.objects.filter(user=request.user).first()
        query_filter = Q(parent=None)
        if vendor:
            query_filter &= Q(vendor=vendor)

        # Search functionality
        search_query = request.GET.get('search', None)
        if search_query:
            query_filter &= (Q(name__icontains=search_query) | Q(description__icontains=search_query))

        # Filter by category
        category = request.GET.get('category', None)
        if category:
            query_filter &= Q(category__id=category)

        # Filter by price range
        min_price = request.GET.get('min_price', None)
        max_price = request.GET.get('max_price', None)
        if min_price:
            query_filter &= Q(price__gte=min_price)
        if max_price:
            query_filter &= Q(price__lte=max_price)

        # Filter by whether the product is active
        is_active = request.GET.get('is_active', None)
        if is_active is not None:
            is_active = is_active.lower() in ['true', '1', 't', 'y', 'yes']
            query_filter &= Q(is_active=is_active)

        # Filter by featured products
        is_featured = request.GET.get('is_featured', None)
        if is_featured is not None:
            is_featured = is_featured.lower() in ['true', '1', 't', 'y', 'yes']
            query_filter &= Q(is_featured=is_featured)

        # Apply all the filters to the products queryset
        products = Product.objects.filter(query_filter)

        # Serialize the filtered products
        # serializer = ProductSerializer(products, many=True, context={'request': request})

        try:
            # Check if vendor exists

            
            return paginate_success_response_with_serializer(
                request,
                ProductSerializer,
                products,
                page_size=int(request.GET.get('page_size', 20)),
                addition_serializer_data={'request': request, 'is_vendor': True}

            )
        except Vendor.DoesNotExist:
            return bad_request_response(message= "Vendor not found")
            
        return success_response(serializer.data)

    @swagger_auto_schema(
        operation_summary="Create a new product for the vendor.",
        operation_description="Create a new product with details such as name, description, price, and category.",
        request_body=ProductSerializer,
        responses={201: ProductSerializer}
    )
    def post(self, request):
        """
        Create a new product for the vendor.

        Body Parameters:
        - name (str): The name of the product.
        - description (str): The description of the product.
        - price (float): The price of the product.
        - category (int): The ID of the product's category.
        - stock (int): The stock quantity of the product.
        - image (file, optional): The image of the product.
        - is_active (bool): Whether the product is active or not.
        - is_featured (bool): Whether the product is featured or not.

        Returns:
        - The newly created product.
        """
        # Handle product data


        print(request.data)
        print(request.headers)
        user = request.user
        # vendor = Vendor.objects.all().first()
        # user = request.user = vendor.user
        # if not user.is_authenticated:
        #     return bad_request_response(
        #         message="You must be logged in to create a product.",
        #         status_code=status.HTTP_401_UNAUTHORIZED,
        #     )

        if not user.is_verified:
            return bad_request_response( 
                message="You must be verified to create a product."
            )

        serializer = self.serializer_class(data=request.data,context={'request': request, 'is_vendor': True})
        serializer.is_valid(raise_exception=True)
        product = serializer.save()

        # Handle product images if present in the request
        images = request.FILES.getlist('images')  # Expecting images as a list of files

        if images:
            # Iterate over the uploaded images and create ProductImage instances
            for index, img in enumerate(images):
                # For the first image, mark it as the primary image
                is_primary = True if index == 0 else False
                
                try:
                    # Upload file to Backblaze B2 and get the URL
                    folder_name = f"products/{product.id}"
                    image_url = upload_to_backblaze(
                        file=img,
                        folder=folder_name,
                        file_name=f"image_{index + 1}_{img.name}"
                    )
                    
                    # Create ProductImage instance with the uploaded image URL
                    ProductImage.objects.create(
                        product=product,
                        image_url=image_url.get('downloadUrl', ''),
                        is_primary=is_primary,
                        is_active=True
                    )
                    
                    logging.info(f"Successfully uploaded image {index + 1} for product {product.id}: {image_url.get('downloadUrl', '')}")
                    
                except Exception as e:
                    # Log the error but continue with other images
                    logging.error(f"Failed to upload image {index + 1} for product {product.id}: {str(e)}")
                    
                    # Create ProductImage instance with empty URL as fallback
                    ProductImage.objects.create(
                        product=product,
                        image_url='',
                        is_primary=is_primary,
                        is_active=False  # Mark as inactive since upload failed
                    )

        return success_response(serializer.data, status_code=status.HTTP_201_CREATED)


class ProductGetUpdateDeleteView(generics.GenericAPIView):
    """
    View to retrieve, update, and delete a product for a vendor.
    """
    permission_classes = [IsVendor]
    serializer_class = ProductSerializer

    @swagger_auto_schema(
        operation_summary="Retrieve a product by its ID.",
        operation_description="Retrieve the details of a product by its unique ID.",
        responses={200: ProductSerializer}
    )
    def get(self, request, product_id):
        """
        Retrieve a product by its ID.

        Parameters:
        - product_id (str): The ID of the product to retrieve.

        Returns:
        - The details of the requested product.
        """
        product = Product.objects.get(id=product_id)
        serializer = ProductSerializer(product,context={'request': request, 'is_vendor': True})
        return success_response(serializer.data)

    @swagger_auto_schema(
        operation_summary="Update a product's details.",
        operation_description="Update the product's details such as name, description, and price.",
        request_body=ProductSerializer,
        responses={200: ProductSerializer}
    )
    def put(self, request, product_id):
        """
        Update a product's information.

        Parameters:
        - product_id (str): The ID of the product to update.
        - Body parameters: Any fields of the product to update (e.g., name, description, price).

        Returns:
        - The updated product.
        """
        print(request.data)
        product = Product.objects.get(id=product_id)
        serializer = ProductSerializer(product, data=request.data, context={'request': request, 'is_vendor': True})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(serializer.data)

    @swagger_auto_schema(
        operation_summary="Partially update a product's details.",
        operation_description="Update one or more fields of a product without modifying the entire object.",
        request_body=ProductSerializer,
        responses={200: ProductSerializer}
    )
    def patch(self, request, product_id):
        product = Product.objects.get(id=product_id)
        serializer = ProductSerializer(product, data=request.data, partial=True, context={'request': request, 'is_vendor': True})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        product_serializer = ProductSerializer(product, context={'request': request, 'is_vendor': True})
        return success_response(product_serializer.data)

    @swagger_auto_schema(
        operation_summary="Delete a product by its ID.",
        operation_description="Delete a product from the vendor's list by its unique ID.",
        responses={204: 'No Content'}
    )
    def delete(self, request, product_id):
        """
        Delete a product by its ID.

        Parameters:
        - product_id (str): The ID of the product to delete.

        Returns:
        - Success message after deletion.
        """
        product = Product.objects.get(id=product_id)
        product.delete()
        return success_response(status_code=status.HTTP_204_NO_CONTENT)





class VendorOrderListView(generics.ListAPIView):
    """
    View to list all orders for a specific vendor.
    - The vendor can filter the orders based on order status, payment status, and date range.
    """
    permission_classes = [IsVendor]  # Assuming IsVendor is a custom permission class for vendors
    serializer_class = OrderSerializer

    
    def get_queryset(self):
        """
        Optionally filter orders for the vendor by status, payment status, or date range.
        """
        vendor = Vendor.objects.get(user=self.request.user) 
        
        queryset = Order.objects.filter(vendor=vendor).order_by('-created_at')
        
        # Filter by order status
        status = self.request.GET.get('status', None)
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by payment status
        payment_status = self.request.GET.get('payment_status', None)
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)
        
        # Filter by date range (created_at)
        start_date = self.request.GET.get('start_date', None)
        end_date = self.request.GET.get('end_date', None)
        if start_date and end_date:
            queryset = queryset.filter(created_at__range=[start_date, end_date])
        
        # Allow for searching by order ID (or other fields if desired)
        order_id = self.request.GET.get('order_id', None)
        if order_id:
            queryset = queryset.filter(id=order_id)

        return queryset

    @swagger_auto_schema(
        operation_summary="Retrieve a list of orders for the vendor.",
        operation_description="Retrieve a list of orders with optional filters for status, payment, and date range.",
        responses={200: OrderSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        """ 
        Return a list of orders for the vendor, with optional filters.
        """
        queryset = self.get_queryset()
        # serializer = self.serializer_class(queryset, many=True)
        # return success_response(data=serializer.data)

        return paginate_success_response_with_serializer(
                request,
                self.serializer_class,
                queryset,
                page_size=int(request.GET.get('page_size', 20))
            )

class VendorPendingOrderListView(generics.ListAPIView):
    """
    View to list all pending orders for a specific vendor.
    """
    permission_classes = [IsVendor]  # Assuming IsVendor is a custom permission class for vendors
    serializer_class = OrderSerializer


    def get_queryset(self):
        vendor = Vendor.objects.only('id').get(user=self.request.user)
        queryset = (
            Order.objects
            .filter(vendor=vendor, status='pending')
            .select_related('vendor', 'user', 'rider')
            .prefetch_related(
                'items',
                'items__product',
                'items__variant_selections',
                'items__variant_selections__variant'
            )
            .order_by('-created_at')
        )

        payment_status = self.request.GET.get('payment_status')
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)

        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        if start_date and end_date:
            queryset = queryset.filter(created_at__range=[start_date, end_date])

        order_id = self.request.GET.get('order_id')
        if order_id:
            queryset = queryset.filter(id=order_id)

        return queryset
    

    @swagger_auto_schema(
        operation_summary="Retrieve a list of orders for the vendor.",
        operation_description="Retrieve a list of orders with optional filters for status, payment, and date range.",
        responses={200: OrderSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        """ 
        Return a list of orders for the vendor, with optional filters.
        """
        queryset = self.get_queryset()
        return paginate_success_response_with_serializer(
                request,
                self.serializer_class,
                queryset,
                page_size=int(request.GET.get('page_size', 20))
            )


class VendorDeliveredOrderListView(generics.ListAPIView):
    """
    View to list all pending orders for a specific vendor.
    """
    permission_classes = [IsVendor]  # Assuming IsVendor is a custom permission class for vendors
    serializer_class = OrderSerializer

    def get_queryset(self):
        vendor = Vendor.objects.only('id').get(user=self.request.user)
        queryset = (
            Order.objects
            .filter(vendor=vendor, status='delivered')
            .select_related('vendor', 'user', 'rider')
            .prefetch_related(
                'items',
                'items__product',
                'items__variant_selections',
                'items__variant_selections__variant'
            )
            .order_by('-created_at')
        )

        payment_status = self.request.GET.get('payment_status')
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)

        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        if start_date and end_date:
            queryset = queryset.filter(created_at__range=[start_date, end_date])

        order_id = self.request.GET.get('order_id')
        if order_id:
            queryset = queryset.filter(id=order_id)

        return queryset

    @swagger_auto_schema(
        operation_summary="Retrieve a list of orders for the vendor.",
        operation_description="Retrieve a list of orders with optional filters for status, payment, and date range.",
        responses={200: OrderSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        """ 
        Return a list of orders for the vendor, with optional filters.
        """
        queryset = self.get_queryset()
        # serializer = self.serializer_class(queryset, many=True)
        # return success_response(data=serializer.data)

        return paginate_success_response_with_serializer(
                request,
                self.serializer_class,
                queryset,
                page_size=int(request.GET.get('page_size', 20))
            )


class VendorInProgressOrderListView(generics.ListAPIView):
    """
    View to list all pending orders for a specific vendor.
    """
    permission_classes = [IsVendor]  # Assuming IsVendor is a custom permission class for vendors
    serializer_class = OrderSerializer

    def get_queryset(self):
        vendor = Vendor.objects.only('id').get(user=self.request.user)
        in_progress_status = [
            'confirmed', 
            'preparing', 
            'looking_for_rider',
            'rider_assigned',
            'picked_up',
            'in_transit',
            'near_delivery'
        ]
        queryset = (
            Order.objects
            .filter(vendor=vendor, status__in=in_progress_status)
            .select_related('vendor', 'user', 'rider')
            .prefetch_related(
                'items',
                'items__product',
                'items__variant_selections',
                'items__variant_selections__variant'
            )
            .order_by('-created_at')
        )

        payment_status = self.request.GET.get('payment_status')
        if payment_status:
            queryset = queryset.filter(payment_status=payment_status)

        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        if start_date and end_date:
            queryset = queryset.filter(created_at__range=[start_date, end_date])

        order_id = self.request.GET.get('order_id')
        if order_id:
            queryset = queryset.filter(id=order_id)

        return queryset

    @swagger_auto_schema(
        operation_summary="Retrieve a list of orders for the vendor.",
        operation_description="Retrieve a list of orders with optional filters for status, payment, and date range.",
        responses={200: OrderSerializer(many=True)}
    )
    def get(self, request, *args, **kwargs):
        """ 
        Return a list of orders for the vendor, with optional filters.
        """
        queryset = self.get_queryset()
        # serializer = self.serializer_class(queryset, many=True)
        # return success_response(data=serializer.data)

        return paginate_success_response_with_serializer(
                request,
                self.serializer_class,
                queryset,
                page_size=int(request.GET.get('page_size', 20))
            )



class GetVendorDetailView(generics.GenericAPIView):
    serializer_class = VendorSerializer
    permission_classes = []
    # permission_classes = [IsAuthenticated]

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
        try:
            vendor = Vendor.objects.get(id=vendor_id)
            serializer = self.serializer_class(vendor)
            return success_response(serializer.data)
        except Vendor.DoesNotExist:
            return bad_request_response(message="Vendor not found")
        

class BuyerVendorProductListView(generics.ListAPIView):
    serializer_class = BuyerVendorProductSerializer
    permission_classes = []
    
    def get_queryset(self):
        vendor_id = self.kwargs.get('vendor_id')
        return Product.objects.filter(parent=None,vendor__id=vendor_id)
    
    @swagger_auto_schema(
        operation_description="Get all products belonging to a specific vendor.",
        operation_summary="Retrieve all products of a vendor.",
        responses={
            200: "List of vendor products",
            404: "Vendor Not Found",
            401: "Unauthorized",
        }
    )
    def get(self, request, vendor_id):
        try:
            # Check if vendor exists
            vendor = Vendor.objects.select_related('category').get(id=vendor_id)

            if request.user.is_authenticated:
                is_vendor = True if vendor.user == request.user else False
            else:
                is_vendor = False

            queryset = (
                Product.objects
                .filter(parent=None, vendor=vendor)
                .select_related('vendor__category')
                .annotate(
                    average_rating_value=Avg('ratings__rating'),
                    total_ratings_value=Count('ratings', distinct=True),
                )
                .prefetch_related(
                    'productimage_set',
                    'productvariantcategory_set__variants',
                    'variants',
                    'ratings',
                )
            )

            return paginate_success_response_with_serializer(
                request,
                self.serializer_class,
                queryset,
                page_size=int(request.GET.get('page_size', 20)),
                addition_serializer_data={'request': request, 'is_vendor': is_vendor}
            )
        except Vendor.DoesNotExist:
            return bad_request_response(message= "Vendor not found")




from math import cos, radians
from django.db.models import Count, Avg
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema

class HotPickVendorsView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = VendorSerializer

    def get_vendor_candidates(self):
        user_lat, user_lon = resolve_request_coordinates(self.request)
        # Exclude marketplace vendors — they don't have a physical local presence
        queryset = approved_vendor_queryset(
            Vendor.objects.filter(is_marketplace=False),
            require_products=True,
            require_location=True,
        )
        search = self.request.query_params.get('search')
        queryset = apply_vendor_search(queryset, search)

        return filter_and_sort_vendors_by_distance(
            queryset,
            user_lat,
            user_lon,
            enforce_delivery_radius=False,
            # BROWSE_RADIUS_KM (10km) — only show vendors near the user
        )

    @swagger_auto_schema(
        operation_description="Get hot pick vendors by combining user favorites, top-rated, and most active vendors.",
        operation_summary="Retrieve hot pick vendors (favorites, top-rated, most active).",
        responses={
            200: VendorSerializer(many=True),
            400: "Bad Request",
            401: "Unauthorized",
        },
        parameters=[
            {
                'name': 'limit',
                'description': 'Limit the number of vendors returned (default is 10).',
                'required': False,
                'type': 'integer',
                'default': 10
            },
            {
                'name': 'latitude',
                'description': 'Latitude coordinate for location-based filtering.',
                'required': False,
                'type': 'number',
                'format': 'float'
            },
            {
                'name': 'longitude',
                'description': 'Longitude coordinate for location-based filtering.',
                'required': False,
                'type': 'number',
                'format': 'float'
            }
        ]
    )
    def get(self, request):
        limit = int(request.GET.get('limit', 10))
        vendor_candidates = self.get_vendor_candidates()
        if not vendor_candidates:
            return paginate_success_response_with_serializer(
                request,
                self.serializer_class,
                [],
                limit
            )

        favorite_vendor_ids = set()
        if request.user.is_authenticated:
            favorite_vendor_ids = set(
                UserFavoriteVendor.objects.filter(user=request.user).values_list(
                    'vendor_id',
                    flat=True,
                )
            )

        ranked_candidates = []
        for vendor, distance in vendor_candidates:
            score = float(vendor.rating or 0)
            if vendor.id in favorite_vendor_ids:
                score += 100
            if vendor.is_featured:
                score += 5
            ranked_candidates.append((vendor, distance, score))

        # Sort: highest score first, distance as tiebreaker, then name
        ranked_candidates.sort(
            key=lambda item: (
                -item[2],   # score descending (rating + boosts)
                item[1],    # distance ascending (nearest among equal scores)
                item[0].name or '',
            )
        )

        # Return top N — keep the rating-first order, no re-sort by distance
        limited_vendors = [vendor for vendor, _, _ in ranked_candidates[:limit]]

        return paginate_success_response_with_serializer(
            request,
            self.serializer_class,
            limited_vendors,
            limit
        )

    def get_user_favorites(self, user, vendors_list):
        # Return empty list if user is not authenticated
        if not user or not isinstance(user, User):
            return []
            
        vendor_ids = [v.id for v in vendors_list]
        favorite_vendor_ids = UserFavoriteVendor.objects.filter(user=user, vendor_id__in=vendor_ids).values_list('vendor_id', flat=True)
        return Vendor.objects.filter(id__in=favorite_vendor_ids)

    def get_top_rated_vendors(self, vendors_list, limit=10):
        vendor_ids = [v.id for v in vendors_list]
        return Vendor.objects.filter(id__in=vendor_ids).annotate(avg_rating=Avg('ratings__rating')).order_by('-avg_rating')[:limit]



class FeaturedVendorsView(generics.GenericAPIView):
    permission_classes = [AllowAny]

    # permission_classes = [IsAuthenticated]
    serializer_class = VendorSerializer
    queryset = Vendor.objects.filter(is_featured=True).annotate(product_count=Count('product')).filter(product_count__gt=0)
    
    def get_queryset(self):
        search = self.request.query_params.get('search')
        user_lat, user_lon = resolve_request_coordinates(self.request)

        # Exclude marketplace vendors — featured is a local browsing section
        featured_queryset = approved_vendor_queryset(
            Vendor.objects.filter(is_featured=True, is_marketplace=False),
            require_products=True,
            require_location=user_lat is not None and user_lon is not None,
        )
        featured_queryset = apply_vendor_search(featured_queryset, search)

        if user_lat is None or user_lon is None:
            return featured_queryset.order_by('-rating', 'name')

        # 10km radius — only show featured vendors near the user
        featured_candidates = filter_and_sort_vendors_by_distance(
            featured_queryset,
            user_lat,
            user_lon,
            enforce_delivery_radius=False,
        )
        if featured_candidates:
            # Nearest first, rating as tiebreaker
            featured_candidates.sort(
                key=lambda item: (item[1], -(float(item[0].rating or 0)), item[0].name or '')
            )
            return [vendor for vendor, _ in featured_candidates]

        # No featured vendors within 10km — fall back to top-rated nearby non-marketplace vendors
        auto_queryset = approved_vendor_queryset(
            Vendor.objects.filter(is_marketplace=False),
            require_products=True,
            require_location=True,
        )
        auto_queryset = apply_vendor_search(auto_queryset, search)
        auto_candidates = filter_and_sort_vendors_by_distance(
            auto_queryset,
            user_lat,
            user_lon,
            enforce_delivery_radius=False,
        )
        auto_candidates.sort(
            key=lambda item: (-(float(item[0].rating or 0)), item[1], item[0].name or '')
        )
        return [vendor for vendor, _ in auto_candidates[:20]]

    @swagger_auto_schema(
        operation_description="Get featured vendors based on location. If latitude and longitude are provided, returns featured vendors within 5km of that location. Otherwise, returns all featured vendors.",
        operation_summary="Get featured vendors",
        manual_parameters=[
            openapi.Parameter('latitude', openapi.IN_QUERY, description="Latitude for location-based filtering", type=openapi.TYPE_NUMBER, format=openapi.FORMAT_FLOAT),
            openapi.Parameter('longitude', openapi.IN_QUERY, description="Longitude for location-based filtering", type=openapi.TYPE_NUMBER, format=openapi.FORMAT_FLOAT),
            openapi.Parameter('search', openapi.IN_QUERY, description="Search term for filtering vendors", type=openapi.TYPE_STRING),
        ],
        responses={
            200: openapi.Response(
                description="Featured vendors retrieved successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'status': openapi.Schema(type=openapi.TYPE_STRING, example='success'),
                        'message': openapi.Schema(type=openapi.TYPE_STRING, example='Featured vendors retrieved successfully'),
                        'data': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)),
                    }
                )
            )
        }
    )
    def get(self, request):
        return paginate_success_response_with_serializer(
            request,
            self.serializer_class,
            self.get_queryset(),
            page_size=20
        )

   


# class AllVendorsView(generics.GenericAPIView):
#     permission_classes = []
#     serializer_class = VendorSerializer

#     def get_queryset(self):
#         queryset = Vendor.objects.annotate(product_count=Count('product')).filter(product_count__gt=0)
#         search = self.request.query_params.get('search')
#         if search:
#             queryset = queryset.filter(
#                 Q(name__icontains=search) |
#                 Q(email__icontains=search) |
#                 Q(city__icontains=search) |
#                 Q(state__icontains=search) |
#                 Q(category__name__icontains=search)
#             )
#         return queryset

#     def get(self, request):
#         return success_response(
#             self.serializer_class(self.get_queryset(), many=True).data
#         )



class AllVendorsView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = VendorSerializer

    def get(self, request):
        from helpers.redis_geo import SEARCH_RADIUS_KM
        search = request.query_params.get('search')
        user_lat, user_lon = resolve_request_coordinates(request)

        # Non-marketplace vendors only for the main listing
        regular_qs = approved_vendor_queryset(
            Vendor.objects.filter(is_marketplace=False),
            require_products=True,
            require_location=True,
        )
        regular_qs = apply_vendor_search(regular_qs, search)

        if user_lat is not None and user_lon is not None:
            # Browsing (no search): 10km — only vendors near the user
            # Searching (keyword): 500km — relevance drives results, not distance
            radius = SEARCH_RADIUS_KM if search else None  # None = default BROWSE_RADIUS_KM
            kwargs = dict(enforce_delivery_radius=False)
            if radius:
                kwargs['radius_km'] = radius
            regular_vendors = nearest_first_vendors(regular_qs, user_lat, user_lon, **kwargs)
        else:
            regular_vendors = list(regular_qs.order_by('-rating', 'name'))

        # Marketplace vendors: only appended when user is searching (no location filter)
        if search:
            marketplace_qs = approved_vendor_queryset(
                Vendor.objects.filter(is_marketplace=True),
                require_products=True,
                require_location=False,
            )
            marketplace_qs = apply_vendor_search(marketplace_qs, search)
            marketplace_vendors = list(marketplace_qs.order_by('-rating', 'name'))

            seen_ids = {v.id for v in regular_vendors}
            for v in marketplace_vendors:
                if v.id not in seen_ids:
                    regular_vendors.append(v)
                    seen_ids.add(v.id)

        data = self.serializer_class(regular_vendors, many=True, context={'request': request}).data
        return success_response(data)



class AllMarketPlaceCategoriesView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = MarketPlaceSerializer

    def get_queryset(self):
        return MarketPlace.objects.filter(is_active=True).order_by('-created_at')

    def get(self, request):
        marketplaces = self.get_queryset()
        data = self.serializer_class(marketplaces, many=True,context={'request': request}).data
        return success_response(data)

class SingleMarketPlaceCategoryView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = MarketPlaceSerializer


    def get(self, request, category_id):
        try:
            marketplace = MarketPlace.objects.get(id=category_id)
        except:
            return bad_request_response(message='Category not found ')
        data = self.serializer_class(marketplace,context={'request': request}).data
        return success_response(data)


class SingleMarketPlaceCategoryVendorsView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = VendorSerializer

    def get(self, request, category_id):
        try:
            marketplace = MarketPlace.objects.get(id=category_id)
        except:
            return bad_request_response(message='Category not found ')

        search = self.request.query_params.get('search')
        queryset = approved_vendor_queryset(
            marketplace.vendors.all(),
            require_products=True,
            require_location=False,
        )
        queryset = apply_vendor_search(queryset, search)

        queryset = list(queryset.order_by('-rating', 'name'))

        data = self.serializer_class(queryset, many=True, context={'request': request}).data
        return success_response(data)




class AllMarketPlaceVendorsView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = VendorSerializer


    def get_queryset(self):
        search = self.request.query_params.get('search')
        queryset = approved_vendor_queryset(
            Vendor.objects.filter(is_marketplace=True),
            require_products=True,
            require_location=True,
        )
        queryset = apply_vendor_search(queryset, search)

        user_lat, user_lon = resolve_request_coordinates(self.request)
        if user_lat is None or user_lon is None:
            return queryset.order_by('-rating', 'name')

        return nearest_first_vendors(queryset, user_lat, user_lon, enforce_delivery_radius=False)


    def get(self, request):
        vendors = self.get_queryset()
        data = self.serializer_class(vendors, many=True,context={'request': request}).data
        return success_response(data)



class AllVendorsNewView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = VendorSerializer
    queryset = Vendor.objects.filter(is_featured=True)


    def get_redis_client(self):
        return redis.Redis.from_url(settings.CACHES['default']['LOCATION'])


    def get_queryset(self):
        user:User = User.objects.get(id=self.request.user.id)

        query_location_latitude = self.request.GET.get('latitude')
        query_location_longitude = self.request.GET.get('longitude')
        query_category = self.request.GET.get('category')

        if not user or not isinstance(user, User):
            if any([not query_location_latitude, not query_location_latitude]):
                return Vendor.objects.none()
            

        if not query_location_latitude or not query_location_longitude:
            user_address = Address.objects.filter(user=user, is_primary=True, is_active=True).first()
            if not user_address:
                return Vendor.objects.none()
            user_lat = user_address.location_latitude
            user_lon = user_address.location_longitude
        else:
            user_lat = query_location_latitude
            user_lon = query_location_longitude

        if user_lat is None or user_lon is None:
            return Vendor.objects.none()

        try:
            user_lat = float(user_lat)
            user_lon = float(user_lon)
        except ValueError:
            return Vendor.objects.none()

        queryset = Vendor.objects.annotate(product_count=Count('product')).filter(
            product_count__gt=0,
            approval_status='approved',
            location_latitude__isnull=False,
            location_longitude__isnull=False
        )

        # Filter by search param
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(email__icontains=search) |
                Q(city__icontains=search) |
                Q(state__icontains=search) |
                Q(category__name__icontains=search)
            )

        if query_category:
            queryset = queryset.filter(Q(category__name__icontains=query_category))

        def distance_check(vendor):
            try:
                dist = get_distance_between_two_location(
                    lat1=user_lat,
                    lon1=user_lon,
                    lat2=float(vendor.location_latitude),
                    lon2=float(vendor.location_longitude)
                )
                return (vendor, dist)
            except (TypeError, ValueError):
                return (vendor, None)

        vendors_within_5km = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(distance_check, vendor) for vendor in queryset]
            for future in as_completed(futures):
                vendor, dist = future.result()
                print(
                    f'Vendor ({vendor.name}) location point ', 
                    vendor.location_latitude,
                    vendor.location_longitude,
                )
                print(
                    'Customer location point ',
                    user_lat,
                    user_lon,
                )
                print('Distance ',dist)
                print('++++++++++++++++++++++')
                if dist is not None and dist <= vendor.delivery_radius_km:
                    vendors_within_5km.append(vendor)

        return vendors_within_5km



    def get(self, request):
        return paginate_success_response_with_serializer(
            request,
            self.serializer_class,
            self.get_queryset(),
            10
        )

   

class AllVendorsNewCachedView(generics.GenericAPIView):
    """
    All-vendors listing using Redis geo for fast proximity queries.
    Falls back to Haversine if Redis is unavailable.
    No delivery-radius enforcement here — this is a browsing endpoint.
    """
    permission_classes = [AllowAny]
    serializer_class = VendorSerializer

    def get(self, request):
        from helpers.redis_geo import SEARCH_RADIUS_KM
        user_lat, user_lon = resolve_request_coordinates(request)
        search = request.query_params.get('search')
        query_category = request.GET.get('category')

        # Exclude marketplace vendors — they don't belong in the local feed
        queryset = approved_vendor_queryset(
            Vendor.objects.filter(is_marketplace=False),
            require_products=True,
            require_location=True,
        )
        queryset = apply_vendor_search(queryset, search)
        if query_category:
            queryset = queryset.filter(Q(category__name__icontains=query_category))

        if user_lat is None or user_lon is None:
            vendors = list(queryset.order_by('-rating', 'name'))
        else:
            radius = SEARCH_RADIUS_KM if search else None
            kwargs = dict(enforce_delivery_radius=False)
            if radius:
                kwargs['radius_km'] = radius
            vendors = nearest_first_vendors(queryset, user_lat, user_lon, **kwargs)

        return paginate_success_response_with_serializer(
            request,
            self.serializer_class,
            vendors,
            10,
        )


class InternalAllVendorsNewView(generics.GenericAPIView):
    permission_classes = []
    serializer_class = VendorSerializer
    queryset = Vendor.objects.filter(is_featured=True)


    def get_queryset(self):
        queryset = Vendor.objects.all().order_by('-created_at')
        search = self.request.query_params.get('search')
        category = self.request.query_params.get('category')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(email__icontains=search) |
                Q(city__icontains=search) |
                Q(state__icontains=search)|
                Q(category__name__icontains=search) |
                Q(category__id__icontains=search)
            )

        if category:
            queryset = queryset.filter(
                Q(category__name__icontains=category) |
                Q(category__id__icontains=category)
            )

        
        return queryset
    
    def get(self, request):
        return paginate_success_response_with_serializer(
            request,
            self.serializer_class,
            self.get_queryset(),
            10
        )

   


class VendorOverviewView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Get vendor overview and performance metrics.",
        operation_summary="Retrieve comprehensive vendor performance data.",
        manual_parameters=[
            openapi.Parameter(
                'time_frame', 
                openapi.IN_QUERY, 
                description="Time period for data (daily, weekly, monthly, yearly)", 
                type=openapi.TYPE_STRING,
                default='weekly'
            ),
        ],
        responses={
            200: "Vendor overview and performance data",
            404: "Vendor Not Found",
            401: "Unauthorized",
        }
    )
    def get(self, request):
        from django.utils import timezone
        user = request.user
        try:
            vendor = Vendor.objects.get(user=user)
        except:
            return bad_request_response(message="Vendor Not Found",status_code=404)
        try:
            time_frame = request.GET.get('time_frame', 'weekly')
            
            # Get date range based on time_frame
            # end_date = timezone.now()
            # if time_frame == 'daily':
            #     start_date = end_date - timedelta(days=1)
            # elif time_frame == 'weekly':
            #     start_date = end_date - timedelta(days=7)
            # elif time_frame == 'monthly':
            #     start_date = end_date - timedelta(days=30)
            # elif time_frame == 'yearly':
            #     start_date = end_date - timedelta(days=365)
            # else:
            #     start_date = end_date - timedelta(days=7)  # Default to weekly
            
            # Get orders for this vendor
            vendor_orders = Order.objects.filter(vendor=vendor)
            
            # Calculate order statistics
            total_orders = vendor_orders.count()
            active_orders = vendor_orders.filter(status='pending').count()
            completed_orders = vendor_orders.filter(status='delivered').count()
            canceled_orders = vendor_orders.filter(status='canceled').count()
            
            # Calculate financial metrics
            total_earnings = vendor_orders.filter(payment_status='paid').aggregate(
                total=Sum('total_amount')
            )['total'] or 0
            
            # Calculate payouts (assuming you have a Payout model or similar)
            # This is a placeholder; adjust according to your actual payment tracking system
            total_payouts = float(total_earnings) * 0.9  # Example: 90% of earnings go to vendor
            pending_payouts = 0  # Placeholder - replace with actual calculation
            
            # Get recent reports or issues (placeholder)
            reports_count = 0  # Replace with actual report count if you have such a feature
            
            # Business details
            business_details = {
                "name": vendor.name,
                "type": vendor.category.name if vendor.category else "Not specified",
                "status": "Active" if vendor.is_active else "Inactive",
                "date_joined": vendor.created_at.strftime("%d/%m/%Y"),
                "rating": float(vendor.rating),
                "logo_url": vendor.thumbnail_url if vendor.thumbnail_url else None
            }
            
            # Order overview
            order_overview = {
                "total_orders": total_orders,
                "active_orders": active_orders,
                "completed_orders": completed_orders,
                "canceled_orders": canceled_orders,
                "time_frame": time_frame
            }
            
            # Sales performance
            sales_performance = {
                "total_earnings": float(total_earnings),
                "total_payouts": float(total_payouts),
                "pending_payouts": pending_payouts,
                "time_frame": time_frame
            }
            
            # Reports
            reports = {
                "count": reports_count,
            }
            
            response_data = {
                "business_details": business_details,
                "order_overview": order_overview,
                "sales_performance": sales_performance,
                "reports": reports
            }
            
            return success_response(data=response_data)
            
        except Vendor.DoesNotExist:
            return bad_request_response(message="Vendor not found")
        except Exception as e:
            print(e)
            return internal_server_error_response()


class VendorOrderDetailAPIView(generics.RetrieveAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    queryset = Order.objects.all()

    @swagger_auto_schema(
        operation_description="Retrieve detailed information of a specific order by ID.",
        operation_summary="Admin Order Detail",
        responses={
            200: OrderSerializer(),
            401: "Unauthorized access.",
            404: "Order not found."
        },
        manual_parameters=[
            openapi.Parameter(
                'id',
                openapi.IN_PATH,
                description="UUID of the order",
                type=openapi.TYPE_STRING,
                required=True
            )
        ]
    )
    def get(self, request, *args, **kwargs):
        try:
            order = self.get_object()
            serializer = self.get_serializer(
                order,
                context={
                    "full_items": True # Use simple item representation
                }
            )
            return success_response(serializer.data)
        except Order.DoesNotExist:
            return bad_request_response(message="Order not found.")

def process_refund(order:Order):
    # Implement your refund logic here, e.g., call payment gateway API to process refund
    transaction = WalletTransaction.objects.filter(order=order).first()

    
    if not transaction:
        print(f"No payment transaction found for order {order.id} to refund.")
        return f"No payment transaction found for order {order.id} to refund."
    
    if transaction.status != 'completed':
        print(f"Transaction for order {order.id} is not completed and cannot be refunded.")
        return f"Transaction for order {order.id} is not completed and cannot be refunded."
    
    wallet, _ = Wallet.objects.get_or_create(user=order.user)
    wallet.balance += transaction.amount
    wallet.save()
    transaction.status = 'refunded'
    transaction.save()

    print(f"Refunded {transaction.amount} to user {order.user.id} for order {order.id}.")


    # add in-app notification
    Notification.objects.create(
        user=order.user,
        title="Order Refund",
        content=f"Your payment of {transaction.amount} for order #{order.track_id} has been refunded."
    )
    return f"Refunded {transaction.amount} to user {order.user.id} for order {order.id}."




class VendorOrderActionAPIView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = VendorOrderActionSerializer

    @swagger_auto_schema(
        operation_summary="Vendor accept or reject an order",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['action'],
            properties={
                'action': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=['accept', 'reject'],
                    description='Action to perform on the order.'
                )
            }
        ),
        responses={
            200: "Action completed successfully.",
            400: "Invalid action or order state.",
            404: "Order not found."
        }
    )
    def post(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id, vendor__user=request.user)
        except Order.DoesNotExist:
            return bad_request_response(message="Order not found or does not belong to this vendor.")

        if order.status != 'pending':
            return bad_request_response(message=f"Cannot modify an order that is already '{order.status}'.")

        action = request.data.get('action')
        if action == 'accept':
            order.status = 'confirmed'
            order.delivery_status = 'confirmed'
            order.save()

            # Notify customer via socket and push
            send_order_accepted_notification_customer(order)


            # order.status = 'looking_for_rider'
            # order.delivery_status = 'awaiting_rider'
            # order.save()

            # send push notification to riders
            send_new_order_push_notification_riders(order)

            order.status = 'looking_for_rider'
            order.save()
            # 


            return success_response(message="Order accepted successfully.")
        
        elif action == 'reject':
            order.status = 'rejected'
            order.delivery_status = 'canceled'
            order.save()

            Notification.objects.create(
                user=order.user,
                title="Order Rejected",
                content=f"Your order #{order.track_id} was rejected by {order.vendor.name}.",
            )



            # refund user if they had already paid
            if order.payment_status == 'paid':
                refund_result = process_refund(order)
                print(f"Refund result for order {order.id}: {refund_result}")

            # Send WebSocket notification to customer
            try:
                from asgiref.sync import async_to_sync
                from channels.layers import get_channel_layer

                customer_group_name = f'customer_{order.user.id}'
                channel_layer = get_channel_layer()

                async_to_sync(channel_layer.group_send)(
                    customer_group_name,
                    {
                        'type': 'order_status_update',
                        'data': {
                            'order_id': str(order.id),
                            'status': 'rejected',
                            'delivery_status': 'canceled',
                            'vendor_name': order.vendor.name,
                            'message': 'Your order was rejected by the vendor.'
                        }
                    }
                )
                print(f"WebSocket rejection notification sent to customer {order.user.id}")
            except Exception as e:
                print(f"WebSocket rejection error: {e}")

            # Send push notification to customer about order rejection
            try:
                result = notification_helper.send_to_user_async(
                    user=order.user,
                    title="Order Rejected",
                    body=f"Your order #{order.track_id} was rejected.",
                    data={
                        "type": "order_status_update",
                        "order_id": str(order.id),
                        "status": "rejected",
                        "delivery_status": "canceled",
                        "vendor_id": str(order.vendor.id),
                        "vendor_name": order.vendor.name,
                        "screen": "order_details",
                        "track_id": str(order.track_id),
                    }
                )
                print(f"Push rejection notification sent: {result}")
            except Exception as e:
                print(f"Push rejection notification error: {e}")

            # Send push notification to vendor confirming the rejection
            try:
                result = notification_helper.send_to_user_async(
                    user=order.vendor.user,
                    title="Order Rejected",
                    body=f"You have rejected order #{order.track_id}.",
                    data={
                        "event": "order_rejected_confirmation",
                        "order_id": str(order.id),
                        "screen": "order_management"
                    }
                )
                print(f"Vendor rejection confirmation sent: {result}")
            except Exception as e:
                print(f"Vendor rejection confirmation error: {e}")

            return success_response(message="Order rejected successfully.")

        else:
            return bad_request_response(message="Invalid action. Use 'accept' or 'reject'.")



class VendorRatingCreateView(generics.CreateAPIView):
    """View for creating vendor ratings"""
    serializer_class = VendorRatingCreateSerializer
    permission_classes = [IsAuthenticated]
    

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

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
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return success_response(
            data=serializer.data,
            message="Vendor rating successfully created."
        )





class VendorRatingListView(generics.ListAPIView):
    """View for listing all ratings for a specific vendor"""
    serializer_class = VendorRatingSerializer
    
    def get_queryset(self):
        vendor_id = self.kwargs['vendor_id']
        return VendorRating.objects.filter(vendor_id=vendor_id).order_by('-created_at')


@api_view(['GET'])
def vendor_rating_stats(request, vendor_id):
    """Get rating statistics for a vendor"""
    try:
        vendor = Vendor.objects.get(id=vendor_id)
        ratings = vendor.ratings.all()
        
        # Rating distribution
        rating_distribution = {}
        for i in range(1, 6):
            count = ratings.filter(rating__gte=i, rating__lt=i+1).count()
            rating_distribution[f'{i}_star'] = count
        
        stats = {
            'average_rating': ratings.aggregate(avg=Avg('rating'))['avg'] or 0,
            'total_ratings': ratings.count(),
            'rating_distribution': rating_distribution,
            'recent_reviews': VendorRatingSerializer(
                ratings.filter(comment__isnull=False).exclude(comment='').order_by('-created_at')[:10], 
                many=True
            ).data
        }
        
        return success_response(data=stats)
    except Vendor.DoesNotExist:
        return bad_request_response(
            message='Vendor not found',
            status_code=404
        )


class VendorThumbnailUploadView(generics.GenericAPIView):
    """
    View to handle vendor thumbnail upload.
    """
    permission_classes = [IsVendor]
    serializer_class = VendorImageUploadSerializer

    @swagger_auto_schema(
        operation_summary="Upload vendor thumbnail",
        operation_description="Upload a thumbnail image for the vendor. The image will be stored in Backblaze B2 and the URL will be saved to the vendor profile.",
        request_body=VendorImageUploadSerializer,
        responses={
            200: openapi.Response(
                description="Thumbnail uploaded successfully",
                examples={
                    "application/json": {
                        "success": True,
                        "message": "Thumbnail uploaded successfully",
                        "data": {
                            "thumbnail_url": "https://f005.backblazeb2.com/file/bucket/vendor_thumbnails/unique_filename.jpg"
                        }
                    }
                }
            ),
            400: openapi.Response(description="Bad request - invalid image or validation error"),
            401: openapi.Response(description="Unauthorized - vendor authentication required"),
            500: openapi.Response(description="Internal server error")
        }
    )
    def post(self, request):
        try:
            # Get the vendor
            vendor = request.user.vendor
            
            # Validate the uploaded image
            serializer = self.serializer_class(data=request.data)
            if not serializer.is_valid():
                return validation_error_response(errors=serializer.errors)
            
            image_file = serializer.validated_data['image']
            
            # Generate unique filename
            import uuid
            import os
            file_extension = os.path.splitext(image_file.name)[1]
            unique_filename = f"vendor_thumbnails/{vendor.id}_{uuid.uuid4()}{file_extension}"
            
            # Upload to Backblaze B2
            upload_result = upload_to_backblaze(image_file, unique_filename)
            
            if not upload_result:
                return internal_server_error_response(
                    message="Failed to upload thumbnail to storage"
                )
            
            # Get the download URL from upload result
            download_url = upload_result.get('downloadUrl')
            
            if not download_url:
                return internal_server_error_response(
                    message="Failed to get download URL from storage"
                )
            
            # Update vendor thumbnail URL
            vendor.thumbnail_url = download_url
            vendor.save()
            
            logging.info(f"Vendor thumbnail uploaded successfully for vendor {vendor.id}: {download_url}")
            
            return success_response(
                message="Thumbnail uploaded successfully",
                data={"thumbnail_url": download_url}
            )
            
        except Vendor.DoesNotExist:
            return bad_request_response(
                message="Vendor profile not found",
                status_code=404
            )
        except Exception as e:
            logging.error(f"Error uploading vendor thumbnail: {str(e)}")
            return internal_server_error_response(
                message="An error occurred while uploading the thumbnail"
            )


class VendorLogoUploadView(generics.GenericAPIView):
    """
    View to handle vendor logo upload.
    """
    permission_classes = [IsVendor]
    serializer_class = VendorImageUploadSerializer

    @swagger_auto_schema(
        operation_summary="Upload vendor logo",
        operation_description="Upload a logo image for the vendor. The image will be stored in Backblaze B2 and the URL will be saved to the vendor profile.",
        request_body=VendorImageUploadSerializer,
        responses={
            200: openapi.Response(
                description="Logo uploaded successfully",
                examples={
                    "application/json": {
                        "success": True,
                        "message": "Logo uploaded successfully",
                        "data": {
                            "logo_url": "https://f005.backblazeb2.com/file/bucket/vendor_logos/unique_filename.jpg"
                        }
                    }
                }
            ),
            400: openapi.Response(description="Bad request - invalid image or validation error"),
            401: openapi.Response(description="Unauthorized - vendor authentication required"),
            500: openapi.Response(description="Internal server error")
        }
    )
    def post(self, request):
        try:
            # Get the vendor
            vendor = request.user.vendor
            
            # Validate the uploaded image
            serializer = self.serializer_class(data=request.data)
            if not serializer.is_valid():
                return validation_error_response(errors=serializer.errors)
            
            image_file = serializer.validated_data['image']
            
            # Generate unique filename
            import uuid
            import os
            file_extension = os.path.splitext(image_file.name)[1]
            unique_filename = f"vendor_logos/{vendor.id}_{uuid.uuid4()}{file_extension}"
            
            # Upload to Backblaze B2
            upload_result = upload_to_backblaze(image_file, unique_filename)
            
            if not upload_result:
                return internal_server_error_response(
                    message="Failed to upload logo to storage"
                )
            
            # Get the download URL from upload result
            download_url = upload_result.get('downloadUrl')
            
            if not download_url:
                return internal_server_error_response(
                    message="Failed to get download URL from storage"
                )
            
            # Update vendor logo URL
            vendor.logo_url = download_url
            vendor.save()
            
            logging.info(f"Vendor logo uploaded successfully for vendor {vendor.id}: {download_url}")
            
            return success_response(
                message="Logo uploaded successfully",
                data={"logo_url": download_url}
            )
            
        except Vendor.DoesNotExist:
            return bad_request_response(
                message="Vendor profile not found",
                status_code=404
            )
        except Exception as e:
            logging.error(f"Error uploading vendor logo: {str(e)}")
            return internal_server_error_response(
                message="An error occurred while uploading the logo"
            )


def send_new_order_push_notification_riders(order):

    """
    Send push notifications to all active and available riders about a new order.

    Args:
        order (Order): The order instance to notify riders about.
    """
    try:
        riders = Rider.objects.filter(active='active')

        def send_notification(rider):
            try:
                notification_helper.send_to_user_async(
                    user=rider.user,
                    title="New order! 🎉",
                    body=f"A new order is available for pickup at {order.vendor.name}.",
                    data={"event": "new_order_event", "order_id": str(order.id)}
                )
            except Exception as e:
                print(f"Push notification error for rider {rider.id}: {e}")

        # Use ThreadPoolExecutor to send notifications concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            executor.map(send_notification, riders)

    except Exception as e:
        print(f"Error sending push notifications to riders: {e}")
