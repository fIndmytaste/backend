import traceback
from helpers.paystack import PaystackManager
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from drf_yasg import openapi
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.db.models import F,Q
from django.db import transaction
from rest_framework.exceptions import ValidationError
from account.models import Address, User, Vendor, VendorRating
from account.serializers import VendorRatingSerializer
from helpers.order_utils import calculate_delivery_fee, get_distance_between_two_location
from product.serializers import CreateOrderSerializer, FavoriteSerializer, FavoriteVendorSerializer, OrderSerializer, RatingSerializer
from vendor.serializers import ProductSerializer, SystemCategorySerializer, VendorSerializer
from wallet.models import WalletTransaction
from .models import UserFavoriteVendor, Order, OrderItem, ProductImage, Rating, SystemCategory, Product, UserFavoriteVendor
from helpers.response.response_format import paginate_success_response_with_serializer,internal_server_error_response, success_response, bad_request_response
from drf_yasg.utils import swagger_auto_schema

from wallet.models import Wallet


class InternalProductListView(generics.GenericAPIView):
    # permission_classes = [IsAuthenticated]
    serializer_class = ProductSerializer
    def get(self, request):
        categories = Product.objects.all()
        serializer = self.serializer_class(categories, many=True)
        return success_response(serializer.data)




class SystemCategoryListView(generics.GenericAPIView):
    # permission_classes = [IsAuthenticated]
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
        products = Product.objects.all()[:5]
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
        products = Product.objects.filter(parent=None,system_category_id=system_category_id)
        serializer = self.serializer_class(products, many=True)
        return success_response(serializer.data)

class DeleteProductImageView(generics.GenericAPIView):

    permission_classes = [IsAuthenticated]


    def delete(self, request, iamge_id):
        try:
            product_image = ProductImage.objects.get(id=iamge_id)
        except:
            return bad_request_response(message="Product image not found")
        
        product_image.delete()
        return success_response(message="Product image deleted successfully",status_code=204)



class VendorBySystemCategoryView(generics.GenericAPIView):
    """
    Endpoint to get vendors by system category.
    """
    serializer_class = VendorSerializer
    permission_classes = [IsAuthenticated]
    queryset = Vendor.objects.all()

    def get_queryset(self):
        queryset = Vendor.objects.all()
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(email__icontains=search) |
                Q(city__icontains=search) |
                Q(state__icontains=search)
            )
        return queryset
    

    @swagger_auto_schema(
        operation_description="Get vendors by system category",
        operation_summary="vendors by system category",
        responses={
            200: VendorSerializer,
        }
    )
    def get(self, request , system_category_id):

        queryset = self.get_queryset().filter(category__id=system_category_id)
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
        filtered_products = self.get_products_by_system_categories(system_categories).filter(parent=None)

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
        favorites = UserFavoriteVendor.objects.filter(user=user)
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
    # permission_classes = [IsAuthenticated]

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



class InternalProductDetailView(generics.GenericAPIView):
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ProductSerializer(data=request.data,context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
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
        products = Product.objects.filter(parent=None,category_id=vendor_category_id)
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
class OrderListCreateView(generics.ListAPIView):
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


class GetDeliveryFeeView(generics.GenericAPIView):
    permission_classes = []
    # permission_classes = [IsAuthenticated]
    def get(self,request,vendor_id):
        user = request.user
        # Get vendor

        user = User.objects.get(email='tester@gmail.com')

        query_location_latitude = request.GET.get('latitude')
        query_location_longitude = request.GET.get('longitude')

        print(
            "Query param data ", query_location_latitude, query_location_longitude
        )
        query_address = request.GET.get('address')

        try:
            vendor = Vendor.objects.get(id=vendor_id)
        except Vendor.DoesNotExist:
            return bad_request_response(message="Vendor not found")

        # Get user address
        
        location_latitude = None
        location_longitude = None

        
        if any([not query_location_latitude, not query_location_longitude]):
            user_address = Address.objects.filter(user=user, is_active=True).first()
            if not user_address:
                return bad_request_response(
                    message="Please set your delivery address in settings before placing an order."
                )
            
            if any([not user_address.location_latitude, not user_address.location_longitude]):
                return bad_request_response(
                    message="Please set your delivery address in settings."
                )
            
            location_latitude = user_address.location_latitude
            location_longitude = user_address.location_longitude 
        else:
            location_latitude = query_location_latitude
            location_longitude = query_location_longitude
        

        print(location_latitude, location_longitude)
        try:
            distance_in_km = get_distance_between_two_location(
                lat1=float(location_latitude),
                lon1=float(location_longitude),
                lat2=float(vendor.location_latitude),
                lon2=float(vendor.location_longitude),
            )
        except Exception as e:
            print(e)
            return bad_request_response(
                message="Failed to calculate delivery fee."
            )

        if distance_in_km is None or distance_in_km > 5: # using 5km range
            return bad_request_response(
                message=f"This vendor cannot deliver to your location (distance too far). Distance {round(distance_in_km or 0 ,2)} km"
            )
        
        delivery_fee = calculate_delivery_fee(distance_in_km)['total_delivery_fee']
        return success_response(
            data={"delivery_fee": delivery_fee},
        )



class CustomerCreateOrderView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CreateOrderSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        query_location_latitude = request.data.get('latitude')
        query_location_longitude = request.data.get('longitude')
        query_address = request.data.get('address')


        print(query_location_latitude,query_location_longitude,query_address)

        user = request.user
        items_data = serializer.validated_data['items']
        vendor_id = serializer.validated_data['vendor_id']

        # Get vendor
        try:
            vendor = Vendor.objects.get(id=vendor_id)
        except Vendor.DoesNotExist:
            return bad_request_response(message="Vendor not found")

        # Get user address
        

        location_latitude = None
        location_longitude = None
        address = None
        
        if any([not query_location_latitude, not query_location_longitude, not query_address]):
            print('++++++'*10)
            user_address = Address.objects.filter(user=user).first()
            if not user_address:
                return bad_request_response(
                    message="Please set your delivery address in settings before placing an order."
                )
            if any([not user_address.location_latitude, not user_address.location_longitude, not user_address.address]):
                return bad_request_response(
                    message="Please set your delivery address in settings."
                )
            
            location_latitude = user_address.location_latitude
            location_longitude = user_address.location_longitude
            address = user_address.address
        else:
            location_latitude = query_location_latitude
            location_longitude = query_location_longitude
            address = query_address
        
        try:
            distance_in_km = get_distance_between_two_location(
                lat1=float(location_latitude),
                lon1=float(location_longitude),
                lat2=float(vendor.location_latitude),
                lon2=float(vendor.location_longitude),
            )

            print(
                f"Vendor location: {vendor.location_latitude}, {vendor.location_longitude}"
            )
            print(
                f"User location: {location_latitude}, {location_longitude}"
            )
            print(
                f"Distance between user and vendor: {round(distance_in_km,3)} km"
            )
        except Exception as e:
            print(e)
            return bad_request_response(
                message="Failed to calculate delivery fee."
            )


        if distance_in_km is None or distance_in_km > 5:
            return bad_request_response(
                message="This vendor cannot deliver to your location (distance too far)."
            )
        

        # product_ids = {item['product'] for item in items_data} 
        
        product_ids = []
        for item in items_data:
            if item.get('variants') not in [[],'',False,None]:
                variants = item['variants']
                for variant in variants:
                    product_ids.append(variant['product'])
            else:
                product_ids.append(item['product'])

        
        print(product_ids)
        # variant_ids = {
        #     variant['product']
        #     for item in items_data if item.get('variants')
        #     for variant in item['variants']
        # }
        # all_ids = list(product_ids.union(variant_ids))
        all_ids = product_ids
        products = Product.objects.filter(id__in=all_ids).select_related('vendor', 'parent') 
        print(products)
        product_map = {str(product.id): product for product in products}
        print(product_map)

        item_count = 0

        try:
            with transaction.atomic():
                
                order = Order.objects.create(user=user, vendor=vendor)

                # Process each item
                for item in items_data:
                    main_product = product_map.get(item['product'])
                    if not main_product:
                        raise ValidationError(f"Product with ID {item['product']} not found.")

                    if main_product.vendor.id != vendor.id:
                        raise ValidationError(f"Product '{main_product.name}' does not belong to the selected vendor.")

                    if item.get('variants'):
                        for variant in item['variants']:
                            variant_product = product_map.get(variant['product'])
                            if not variant_product:
                                raise ValidationError(f"Variant with ID {variant['product']} not found.")

                            if not variant_product.parent or variant_product.parent.id != main_product.id:
                                raise ValidationError(f"Variant {variant['product']} is not linked to product {main_product.id}.")

                            if variant_product.vendor.id != vendor.id:
                                raise ValidationError(f"Variant '{variant_product.name}' does not belong to the selected vendor.")

                            OrderItem.objects.create(
                                order=order,
                                product=variant_product,
                                quantity=variant['quantity'],
                                price=variant_product.price
                            )
                            item_count += variant['quantity']
                    else:
                        OrderItem.objects.create(
                            order=order,
                            product=main_product,
                            quantity=item['quantity'],
                            price=main_product.price
                        )
                        item_count += item['quantity']

                # Calculate delivery and finalize order
                delivery_fee = calculate_delivery_fee(distance_in_km)['total_delivery_fee']
                # delivery_fee = calculate_delivery_fee(distance_in_km, item_count)
                order.update_total_amount()
                order.address = address
                order.location_latitude = location_latitude
                order.location_longitude = location_longitude
                order.delivery_fee = delivery_fee
                order.save()

                return success_response(
                    message="Order created successfully",
                    data=OrderSerializer(order).data
                )

        except ValidationError as ve:
            return bad_request_response(message=str(ve))

        except Exception as e:
            traceback_str = traceback.format_exc()
            print(traceback_str)
            return internal_server_error_response(message="An error occurred while creating your order.")



class CustomerCreateOrderMobileView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CreateOrderSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        query_location_latitude = request.GET.get('latitude') or request.data.get('latitude') 
        query_location_longitude = request.GET.get('longitude') or request.data.get('longitude') 
        query_address = request.GET.get('address') or request.data.get('address')

        user = request.user
        items_data = serializer.validated_data['items']
        vendor_id = serializer.validated_data['vendor_id']

        # Get vendor
        try:
            vendor = Vendor.objects.get(id=vendor_id)
        except Vendor.DoesNotExist:
            return bad_request_response(message="Vendor not found")

        # Get user address
        

        location_latitude = None
        location_longitude = None
        address = None
        
        if any([not query_location_latitude, not query_location_longitude, not query_address]):
            user_address = Address.objects.filter(user=request.user,is_active=True).first()

            if not user_address:
                return bad_request_response(
                    message="Please set your delivery address in settings before placing an order."
                )

            print(user_address.location_latitude, user_address.location_longitude)
            if any([not user_address.location_latitude, not user_address.location_longitude]):
                return bad_request_response(
                    message="Please set your delivery address in settings."
                )
            
            location_latitude = user_address.location_latitude
            location_longitude = user_address.location_longitude
            address = user_address.address
        else:
            location_latitude = query_location_latitude
            location_longitude = query_location_longitude
            address = query_address
        
        try:
            distance_in_km = get_distance_between_two_location(
                lat1=float(location_latitude),
                lon1=float(location_longitude),
                lat2=float(vendor.location_latitude),
                lon2=float(vendor.location_longitude),
            )
        except Exception as e:
            print(e)
            return bad_request_response(
                message="Failed to calculate delivery fee."
            )

        print(distance_in_km)
        if distance_in_km is None or distance_in_km > 5:
            return bad_request_response(
                message="This vendor cannot deliver to your location (distance too far)."
            )

        product_ids = []
        for item in items_data:
            if item.get('variants') not in [[],'',False,None]:
                variants = item['variants']
                for variant in variants:
                    product_ids.append(variant['product'])
            else:
                product_ids.append(item['product'])

        all_ids = product_ids
        products = Product.objects.filter(id__in=all_ids).select_related('vendor', 'parent') 
        product_map = {str(product.id): product for product in products}

        item_count = 0

        try:
            with transaction.atomic():
                
                order = Order.objects.create(user=user, vendor=vendor)

                # Process each item
                for item in items_data:
                    main_product = product_map.get(item['product'])
                    if not main_product:
                        raise ValidationError(f"Product with ID {item['product']} not found.")

                    if main_product.vendor.id != vendor.id:
                        raise ValidationError(f"Product '{main_product.name}' does not belong to the selected vendor.")

                    if item.get('variants'):
                        for variant in item['variants']:
                            variant_product = product_map.get(variant['product'])
                            if not variant_product:
                                raise ValidationError(f"Variant with ID {variant['product']} not found.")

                            if not variant_product.parent or variant_product.parent.id != main_product.id:
                                raise ValidationError(f"Variant {variant['product']} is not linked to product {main_product.id}.")

                            if variant_product.vendor.id != vendor.id:
                                raise ValidationError(f"Variant '{variant_product.name}' does not belong to the selected vendor.")

                            OrderItem.objects.create(
                                order=order,
                                product=variant_product,
                                quantity=variant['quantity'],
                                price=variant_product.price
                            )
                            item_count += variant['quantity']
                    else:
                        OrderItem.objects.create(
                            order=order,
                            product=main_product,
                            quantity=item['quantity'],
                            price=main_product.price
                        )
                        item_count += item['quantity']

                # Calculate delivery and finalize order
                delivery_fee = calculate_delivery_fee(distance_in_km, item_count)['total_delivery_fee']
                order.update_total_amount()
                order.address = address
                order.location_latitude = location_latitude
                order.location_longitude = location_longitude
                order.payment_method = request.data.get('payment_method','wallet')
                order.delivery_fee = delivery_fee
                order.save()

                order_total_price = float(order.get_total_price()) + order.delivery_fee + order.service_fee

                if request.data.get('payment_method') != 'wallet' and order.payment_method == 'wallet':
                    wallet, _ = Wallet.objects.get_or_create(user=user)
                    
                    if float(order_total_price) > float(wallet.balance):
                        raise ValueError('Insufficient balance. Please top up your wallet')
                    
                    # proceed the payment
                    wallet.balance -= order_total_price
                    wallet.save()
                    order.status = 'paid'
                    order.save()

                    WalletTransaction.objects.create(
                        wallet=wallet, 
                        amount=order_total_price,
                        transaction_type='purchase',
                        description='Payment for order',
                        status='completed',
                        order=order
                    )

                    try:
                        channel_layer = get_channel_layer()
                        vendor_group_name = f'vendor_{vendor.user.id}'

                        async_to_sync(channel_layer.group_send)(
                            vendor_group_name,
                            {
                                'type': 'new_order_notification',
                                'data': {
                                    'order_id': str(order.id),
                                    'customer': {
                                        'name': order.user.full_name,
                                        'phone': order.user.phone_number
                                    },
                                    'delivery_address': order.address,
                                    'created_at': order.created_at.isoformat(),
                                    'status': order.status,
                                }
                            }
                        )

                    except Exception as e:
                        print(e)

                    return success_response(
                        message='Payment successful'
                    )
                else:
                    klass = PaystackManager()
                    order.payment_method = 'link'
                    order.save()
                    return klass.initiate_payment(request, order_total_price, order,is_mobile=True)


        except ValidationError as ve:
            return bad_request_response(message=str(ve))
        except ValueError as ve:
            return bad_request_response(message=str(ve))


        except Exception as e:
            traceback_str = traceback.format_exc()
            print(traceback_str)
            return internal_server_error_response(message="An error occurred while creating your order.")


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
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['include_delivery_info'] = True
        context['requested_by'] = self.request.user.username
        return context
    
    def get_queryset(self):
        """Only return orders belonging to the authenticated user."""
        return Order.objects.filter(user=self.request.user)


class UserFavoriteListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FavoriteVendorSerializer

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
        return UserFavoriteVendor.objects.filter(user=self.request.user).order_by('-created_at')


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
    def post(self, request):
        """
        Add a product to the user's favorites.
        """
        product_id = request.data.get('vendor_id')
        try:
            vendor = Vendor.objects.get(id=product_id)
        except Vendor.DoesNotExist:
            return bad_request_response(message="Vendor not found.")

        # Check if the product is already in the user's favorites
        if UserFavoriteVendor.objects.filter(user=request.user, vendor=vendor).exists():
            return bad_request_response(message="Product is already in your favorites.")

        favorite = UserFavoriteVendor.objects.create(user=request.user, vendor=vendor)
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
    def delete(self, request):
        product_id = request.data.get('vendor_id')
        try:
            vendor = Vendor.objects.get(id=product_id)
        except Vendor.DoesNotExist:
            return bad_request_response(message="Product not found.")

        existing_product = UserFavoriteVendor.objects.filter(user=request.user, vendor=vendor).first()

        if not existing_product:
            return bad_request_response(message="Product is not in your favorites.")

        existing_product.delete()
        return success_response(message="Product removed from your favorites.", status_code=204)

class CustomerUpdateOrderView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CreateOrderSerializer

    def put(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except Order.DoesNotExist:
            return bad_request_response(message="Order not found.")

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        query_location_latitude = request.data.get('latitude')
        query_location_longitude = request.data.get('longitude')
        query_address = request.data.get('address')

        user = request.user
        items_data = serializer.validated_data['items']
        vendor_id = serializer.validated_data['vendor_id']

        # Get vendor
        try:
            vendor = Vendor.objects.get(id=vendor_id)
        except Vendor.DoesNotExist:
            return bad_request_response(message="Vendor not found")

        # Get user address
        location_latitude = None
        location_longitude = None
        address = None

        if any([not query_location_latitude, not query_location_longitude, not query_address]):
            user_address = Address.objects.filter(user=user).first()
            if not user_address:
                return bad_request_response(
                    message="Please set your delivery address in settings before placing an order."
                )
            if any([not user_address.location_latitude, not user_address.location_longitude, not user_address.address]):
                return bad_request_response(
                    message="Please set your delivery address in settings."
                )
            location_latitude = user_address.location_latitude
            location_longitude = user_address.location_longitude
            address = user_address.address
        else:
            location_latitude = query_location_latitude
            location_longitude = query_location_longitude
            address = query_address

        try:
            distance_in_km = get_distance_between_two_location(
                lat1=float(location_latitude),
                lon1=float(location_longitude),
                lat2=float(vendor.location_latitude),
                lon2=float(vendor.location_longitude),
            )
        except Exception as e:
            print(e)
            return bad_request_response(
                message="Failed to calculate delivery fee."
            )

        if distance_in_km is None or distance_in_km > 5:
            return bad_request_response(
                message="This vendor cannot deliver to your location (distance too far)."
            )

        product_ids = []
        for item in items_data:
            if item.get('variants') not in [[], '', False, None]:
                variants = item['variants']
                for variant in variants:
                    product_ids.append(variant['product'])
            else:
                product_ids.append(item['product'])

        products = Product.objects.filter(id__in=product_ids).select_related('vendor', 'parent')
        product_map = {str(product.id): product for product in products}

        item_count = 0

        try:
            with transaction.atomic():
                # Clear existing order items
                OrderItem.objects.filter(order=order).delete()

                # Update order vendor if changed
                order.vendor = vendor

                # Process each item
                for item in items_data:
                    main_product = product_map.get(item['product'])
                    if not main_product:
                        raise ValidationError(f"Product with ID {item['product']} not found.")

                    if main_product.vendor.id != vendor.id:
                        raise ValidationError(f"Product '{main_product.name}' does not belong to the selected vendor.")

                    if item.get('variants'):
                        for variant in item['variants']:
                            variant_product = product_map.get(variant['product'])
                            if not variant_product:
                                raise ValidationError(f"Variant with ID {variant['product']} not found.")

                            if not variant_product.parent or variant_product.parent.id != main_product.id:
                                raise ValidationError(f"Variant {variant['product']} is not linked to product {main_product.id}.")

                            if variant_product.vendor.id != vendor.id:
                                raise ValidationError(f"Variant '{variant_product.name}' does not belong to the selected vendor.")

                            OrderItem.objects.create(
                                order=order,
                                product=variant_product,
                                quantity=variant['quantity'],
                                price=variant_product.price
                            )
                            item_count += variant['quantity']
                    else:
                        OrderItem.objects.create(
                            order=order,
                            product=main_product,
                            quantity=item['quantity'],
                            price=main_product.price
                        )
                        item_count += item['quantity']

                # Calculate delivery and finalize order
                delivery_fee = calculate_delivery_fee(distance_in_km)['total_delivery_fee']
                order.address = address
                order.location_latitude = location_latitude
                order.location_longitude = location_longitude
                order.delivery_fee = delivery_fee
                order.save()
                order.update_total_amount()

                return success_response(
                    message="Order updated successfully",
                    data=OrderSerializer(order).data
                )

        except ValidationError as ve:
            return bad_request_response(message=str(ve))

        except Exception as e:
            traceback_str = traceback.format_exc()
            print(traceback_str)
            return internal_server_error_response(message="An error occurred while updating your order.")
