from rest_framework import status, generics 
from django.db.models import Q, Avg,Sum, Count
from account.models import Address, User, Vendor, VendorRating
from account.serializers import VendorRatingSerializer
from helpers.order_utils import get_distance_between_two_location
from helpers.permissions import IsVendor
from rest_framework.permissions import IsAuthenticated, AllowAny
from product.models import Order, Product, ProductImage, SystemCategory, VendorCategory
from product.serializers import OrderSerializer
from .serializers import VendorCategorySerializer, ProductSerializer, VendorRatingCreateSerializer,VendorRegisterBusinessSerializer, VendorSerializer
from helpers.response.response_format import internal_server_error_response, success_response, bad_request_response,paginate_success_response_with_serializer
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi 
from datetime import timedelta
from rest_framework.decorators import api_view
from math import radians, cos
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
    permission_classes = [IsVendor]  
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
        query_filter = Q(parent=None)

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
        serializer = ProductSerializer(products, many=True, context={'request': request})
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


        user = request.user
        if not user.is_verified:
            return bad_request_response(
                message="You must be verified to create a product."
            )
        print("********"*10)
        print(request.data)
        print("********"*10)
        serializer = self.serializer_class(data=request.data,context={'request': request})
        serializer.is_valid(raise_exception=True)
        product = serializer.save()

        # Handle product images if present in the request
        images = request.FILES.getlist('images')  # Expecting images as a list of files

        if images:
            # Iterate over the uploaded images and create ProductImage instances
            for index, img in enumerate(images):
                # For the first image, mark it as the primary image
                is_primary = True if index == 0 else False
                ProductImage.objects.create(
                    product=product,
                    image=img,
                    is_primary=is_primary,
                    is_active=True
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
        serializer = ProductSerializer(product,context={'request': request})
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
        product = Product.objects.get(id=product_id)
        serializer = ProductSerializer(product, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(serializer.data)

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
        serializer = self.serializer_class(queryset, many=True)
        return success_response(data=serializer.data)



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
    serializer_class = ProductSerializer  # Assuming you have a ProductSerializer
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
            vendor = Vendor.objects.get(id=vendor_id)

            
            return paginate_success_response_with_serializer(
                request,
                self.serializer_class,
                Product.objects.filter(parent=None,vendor=vendor),
                page_size=int(request.GET.get('page_size', 20))
            )
        except Vendor.DoesNotExist:
            return bad_request_response(message= "Vendor not found")




class HotPickVendorsView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = VendorSerializer

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
            }
        ]
    )
    def get(self, request):
        limit = int(request.GET.get('limit', 10))

        # Get the user's favorited vendors
        favorite_vendors = list(self.get_user_favorites(request.user))

        # Get top-rated vendors
        top_rated_vendors = list(self.get_top_rated_vendors(limit))

        # Get most active vendors
        most_active_vendors = list(self.get_most_active_vendors(limit))

        # Combine vendors: Avoid duplicates using set()
        combined_vendors = set(favorite_vendors + top_rated_vendors + most_active_vendors)

        # Limit the results to 'limit' number of vendors
        # return success_response(data=self.serializer_class(list(combined_vendors)[:limit], many=True).data)
        return paginate_success_response_with_serializer(
            request,
            self.serializer_class,
            list(combined_vendors)[:limit],
            limit
        )

    def get_user_favorites(self, user):
        """
        Get all the user's favorited vendors.
        """
        return []

    def get_top_rated_vendors(self, limit=10):
        """
        Get the top-rated vendors based on their average rating.
        """
        return Vendor.objects.annotate(avg_rating=Avg('ratings__rating')).order_by('-avg_rating')[:limit]

    def get_most_active_vendors(self, limit=10):
        """
        Get the most active vendors (e.g., based on recent updates or activity).
        """
        return Vendor.objects.filter(is_active=True).order_by('-updated_at')[:limit]






class FeaturedVendorsView(generics.GenericAPIView):
    permission_classes = [AllowAny]

    # permission_classes = [IsAuthenticated]
    serializer_class = VendorSerializer
    queryset = Vendor.objects.filter(is_featured=True).annotate(product_count=Count('product')).filter(product_count__gt=0)
    
    def get_queryset(self):
        user:User = self.request.user
        if not user or not isinstance(user, User):
            return Vendor.objects.filter(is_featured=True).annotate(product_count=Count('product')).filter(product_count__gt=0)
        
        user_address, _ = Address.objects.get_or_create(user=user)
        user_lat = user_address.location_latitude
        user_lon = user_address.location_longitude
        if user_lat is None or user_lon is None:
            return Vendor.objects.none() 

        try:
            user_lat = float(user_lat)
            user_lon = float(user_lon)
        except ValueError:
            return Vendor.objects.none()

        # Approximate latitude/longitude delta for 10 km radius
        # 1 degree latitude ~= 111 km
        lat_delta = 10 / 111  # ~0.09 degrees
        # 1 degree longitude varies, use cos(lat) for approximation
        lon_delta = 10 / (111 * cos(radians(user_lat)))

        # Filter vendors roughly in bounding box first
        queryset = Vendor.objects.annotate(product_count=Count('product')).filter(
            product_count__gt=0,
            location_latitude__isnull=False,
            location_longitude__isnull=False,
            location_latitude__gte=user_lat - lat_delta,
            location_latitude__lte=user_lat + lat_delta,
            location_longitude__gte=user_lon - lon_delta,
            location_longitude__lte=user_lon + lon_delta,
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

        # Now filter queryset in Python using exact haversine distance
        vendors_within_10km = []
        for vendor in queryset:
            try:
                v_lat = float(vendor.location_latitude)
                v_lon = float(vendor.location_longitude)
            except (TypeError, ValueError):
                continue

        dist = get_distance_between_two_location(
            lat1=user_lat, lon1=user_lon,
            lat2=v_lat, lon2=v_lon
        )
        if dist is not None and dist <= 10:
            vendors_within_10km.append(vendor)

        return vendors_within_10km

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
    permission_classes = []
    serializer_class = VendorSerializer

    def get_queryset(self):
        user:User = self.request.user
        print("+++++"*20)
        print(user)
        print(type(user))
        if not user or not isinstance(user, User):
            return Vendor.objects.filter(is_featured=True).annotate(product_count=Count('product')).filter(product_count__gt=0)
        
        user_address, _ = Address.objects.get_or_create(user=user)
        user_lat = user_address.location_latitude
        user_lon = user_address.location_longitude

        if user_lat is None or user_lon is None:
            return Vendor.objects.none()  # or return all vendors if you prefer

        try:
            user_lat = float(user_lat)
            user_lon = float(user_lon)
        except ValueError:
            return Vendor.objects.none()

        # Approximate latitude/longitude delta for 10 km radius
        # 1 degree latitude ~= 111 km
        lat_delta = 10 / 111  # ~0.09 degrees
        # 1 degree longitude varies, use cos(lat) for approximation
        lon_delta = 10 / (111 * cos(radians(user_lat)))

        # Filter vendors roughly in bounding box first
        queryset = Vendor.objects.annotate(product_count=Count('product')).filter(
            product_count__gt=0,
            location_latitude__isnull=False,
            location_longitude__isnull=False,
            location_latitude__gte=user_lat - lat_delta,
            location_latitude__lte=user_lat + lat_delta,
            location_longitude__gte=user_lon - lon_delta,
            location_longitude__lte=user_lon + lon_delta,
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

        # Now filter queryset in Python using exact haversine distance
        vendors_within_10km = []
        for vendor in queryset:
            try:
                v_lat = float(vendor.location_latitude)
                v_lon = float(vendor.location_longitude)
            except (TypeError, ValueError):
                continue

            dist = get_distance_between_two_location(
                lat1=user_lat, lon1=user_lon,
                lat2=v_lat, lon2=v_lon
            )
            if dist is not None and dist <= 10:
                vendors_within_10km.append(vendor)

        return vendors_within_10km

    def get(self, request):
        vendors = self.get_queryset()
        data = self.serializer_class(vendors, many=True).data
        return success_response(data)


   

class AllVendorsNewView(generics.GenericAPIView):
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
            end_date = timezone.now()
            if time_frame == 'daily':
                start_date = end_date - timedelta(days=1)
            elif time_frame == 'weekly':
                start_date = end_date - timedelta(days=7)
            elif time_frame == 'monthly':
                start_date = end_date - timedelta(days=30)
            elif time_frame == 'yearly':
                start_date = end_date - timedelta(days=365)
            else:
                start_date = end_date - timedelta(days=7)  # Default to weekly
            
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
                "logo_url": request.build_absolute_uri(vendor.logo.url) if vendor.logo else None
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
            serializer = self.get_serializer(order)
            return success_response(serializer.data)
        except Order.DoesNotExist:
            return bad_request_response(message="Order not found.")






class VendorRatingCreateView(generics.CreateAPIView):
    """View for creating vendor ratings"""
    serializer_class = VendorRatingCreateSerializer
    permission_classes = [IsAuthenticated]
    
    def perform_create(self, serializer):
        serializer.save()


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

