# --- New View: CustomerCreateOrderWithVariantsView ---

from decimal import Decimal
import traceback
from helpers.paystack import PaystackManager
from helpers.websocket_notification import send_order_accepted_notification_customer
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_yasg import openapi
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.db.models import F,Q, Avg,Sum, Count
from django.db import transaction
from rest_framework.exceptions import ValidationError
from account.models import Address, User, Vendor, VendorRating,VendorIssueReporting
from account.serializers import VendorIssueReportSerializer, VendorRatingSerializer
from helpers.order_utils import apply_promo_code, calculate_delivery_fee, get_distance_between_two_location, calculate_rider_fare
from product.promo_models import PromoCode
from product.serializers import CreateOrderSerializer, FavoriteSerializer, FavoriteVendorSerializer, OrderSerializer, PromoCodeSerializer, RatingSerializer
from vendor.models import MarketPlace
from vendor.serializers import ProductSerializer, SystemCategorySerializer, VendorSerializer
from wallet.models import WalletTransaction
from .models import DeliveryFee, UserFavoriteVendor, Order, OrderItem, ProductImage, Rating, SystemCategory, Product, UserFavoriteVendor
from helpers.response.response_format import paginate_success_response_with_serializer,internal_server_error_response, success_response, bad_request_response
from drf_yasg.utils import swagger_auto_schema
from helpers.push_notification import notification_helper,send_order_payment_success_notification
from wallet.models import Wallet
from rest_framework.exceptions import NotFound

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



from .models import ProductVariant, OrderItemVariant

class CustomerCreateOrderWithVariantsView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CreateOrderSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        items_data = request.data['items']
        vendor_id = serializer.validated_data['vendor_id']

        # Get vendor
        try:
            vendor = Vendor.objects.get(id=vendor_id)
        except Vendor.DoesNotExist:
            return bad_request_response(message="Vendor not found")

        # Address logic (reuse from existing view)
        query_location_latitude = request.GET.get('latitude') or request.data.get('latitude') 
        query_location_longitude = request.GET.get('longitude') or request.data.get('longitude') 
        query_address = request.GET.get('address') or request.data.get('address')
        delivery_fee_id = request.data.get('delivery_fee_id')

        delivery_fee = None
        if delivery_fee_id:
            try:
                delivery_fee_record = DeliveryFee.objects.get(id=delivery_fee_id, user=user, vendor=vendor, is_active=True )
            except DeliveryFee.DoesNotExist:
                # l = DeliveryFee.objects.create(
                #     user=user,
                #     amount=Decimal('2014.27'),
                #     vendor=vendor,
                # )
                # print(f"Created new delivery fee record: {l}")
                # print(f"Created new delivery fee record: {l.id}")
                # print(f"Created new delivery fee record: {l}")
                # print(f"Created new delivery fee record: {l}")
                return bad_request_response(message="Invalid delivery fee option selected.")
            

            delivery_fee = delivery_fee_record.amount

        location_latitude = None
        location_longitude = None
        address = None
        if any([not query_location_latitude, not query_location_longitude]):
            user_address = Address.objects.filter(user=request.user,is_active=True).first()
            if not user_address:
                return bad_request_response(message="Please set your delivery address in settings before placing an order.")
            if any([not user_address.location_latitude, not user_address.location_longitude]):
                return bad_request_response(message="Please set your delivery address in settings.")
            location_latitude = user_address.location_latitude
            location_longitude = user_address.location_longitude
            address = user_address.address
        else:
            location_latitude = query_location_latitude
            location_longitude = query_location_longitude
            address = query_address

        print('Vendor location:', vendor.location_latitude, vendor.location_longitude )
        try:
            distance_in_km = get_distance_between_two_location(
                lat1=float(location_latitude),
                lon1=float(location_longitude),
                lat2=float(vendor.location_latitude),
                lon2=float(vendor.location_longitude),
            )
        except Exception as e:
            print(e)
            return bad_request_response(message=f"Failed to calculate delivery fee. {str(e)}")

        if distance_in_km is None or distance_in_km > vendor.delivery_radius_km:
            return bad_request_response(message="This vendor cannot deliver to your location (distance too far).")

        # --- Main logic for ProductVariant/OrderItemVariant ---
        main_product_ids = [item['product'] for item in items_data]
        main_products = Product.objects.filter(id__in=main_product_ids, vendor=vendor)
        product_map = {str(product.id): product for product in main_products}

        # Collect all variant IDs
        variant_ids = []
        for item in items_data:
            for variant in item.get('variants', []):
                variant_ids.append(variant['variant'])
        variant_objs = ProductVariant.objects.filter(id__in=variant_ids)
        variant_map = {str(variant.id): variant for variant in variant_objs}

        item_count = 0

        order = None

        try:
            with transaction.atomic():
                order = Order.objects.create(user=user, vendor=vendor)

                for item in items_data:
                    main_product = product_map.get(item['product'])
                    if not main_product:
                        raise ValidationError(f"Product with ID {item['product']} not found.")

                    # Create OrderItem for the main product
                    order_item = OrderItem.objects.create(
                        order=order,
                        product=main_product,
                        quantity=item.get('quantity', 1),
                        price=main_product.get_price_with_commission()
                    )
                    item_count += item.get('quantity', 1)

                    # For each variant selection, create OrderItemVariant
                    for variant in item.get('variants', []):
                        variant_obj = variant_map.get(variant['variant'])
                        if not variant_obj:
                            raise ValidationError(f"Variant with ID {variant['variant']} not found.")
                        if variant_obj.product.id != main_product.id:
                            raise ValidationError(f"Variant {variant_obj.name} does not belong to product {main_product.name}.")
                        if not variant_obj.is_active:
                            raise ValidationError(f"Variant {variant_obj.name} is not active.")
                        # if variant_obj.stock < variant['quantity']:
                        #     raise ValidationError(f"Not enough stock for variant {variant_obj.name}. Available: {variant_obj.stock}, Requested: {variant['quantity']}")
             
                        OrderItemVariant.objects.create(
                            order_item=order_item,
                            variant=variant_obj,
                            quantity=variant['quantity'],
                            price_at_purchase=variant_obj.get_price_with_commission()
                        )
                        # Decrement stock
                        # variant_obj.stock -= variant['quantity']
                        variant_obj.save()
                        item_count += variant['quantity']

                promo_code = request.data.get('promo_code')
                
                # Delivery fee calculation (reuse logic)
                original_delivery_fee = Decimal('0.00')
                promo_info = {"is_applied": False, "discount_amount": 0}

                # order_total_price = order.get_total_price()  # Calculate total price based on OrderItems and OrderItemVariants
                
                order_total_price_without_delivery_fee = float(order.get_total_price()) + order.service_fee
                order_total_price = float(order.get_total_price()) + (delivery_fee or order.delivery_fee) + order.service_fee

                print(
                    f"Initial order total price (before promo): {order_total_price}, item_count: {item_count}, delivery_fee: {delivery_fee}, promo_code: {promo_code}"
                )
                # from product.promo_models import PromoUsage 
                # PromoUsage.objects.all().delete() 
                if not delivery_fee and promo_code:
                    delivery_fee_response = order.vendor.calculate_delivery_fee_by_vendor(
                        item_count, 
                        dest_lat=float(location_latitude), 
                        dest_lon=float(location_longitude),
                        user=user,
                        promo_code=promo_code,
                        order_value=float(order_total_price)
                    )
                    delivery_fee = delivery_fee_response["total_fee"]
                    original_delivery_fee = delivery_fee_response["original_fee"]
                    promo_info = delivery_fee_response["promo_info"]
                    promo_info['original_price'] = order_total_price 
                    original_delivery_fee = delivery_fee 


                if promo_code:
                    promo_info = apply_promo_code(
                        promo_code, 
                        user, 
                        order_total_price_without_delivery_fee, 
                        distance_in_km, 
                        order.vendor, 
                        delivery_fee
                    )

                print(promo_info)
                if promo_info["is_applied"]:
                    from product.promo_models import PromoCode
                    promo_obj = PromoCode.objects.filter(code__iexact=promo_info["code"]).first()
                    order.promo_code = promo_obj
                    order.promo_discount_amount = promo_info["discount_amount"]
                    print(f"Applied promo code: {promo_obj.code}, discount amount: {promo_info['discount_amount']}")

                order.update_total_amount()
                order.address = address
                order.location_latitude = location_latitude
                order.location_longitude = location_longitude
                order.delivery_fee = delivery_fee
                order.original_delivery_fee = original_delivery_fee
                
                
                dist = 0.0
                try:
                    dist = get_distance_between_two_location(
                        lat1=float(vendor.location_latitude),
                        lon1=float(vendor.location_longitude),
                        lat2=float(location_latitude),
                        lon2=float(location_longitude),
                    )
                except: pass
                order.rider_earning = calculate_rider_fare(dist)
                
                order.payment_method = request.data.get('payment_method','wallet')
                order.note = request.data.get('note',request.data.get('notes'))
                order.save()

                if order.promo_code:
                    from product.promo_models import PromoUsage
                    PromoUsage.objects.create(
                        promo=order.promo_code,
                        user=user,
                        order=order,
                        discount_amount=order.promo_discount_amount or 0,
                        original_amount=float(order_total_price) + float(order.delivery_fee),
                        final_amount=float(order_total_price) + float(order.delivery_fee) - float(order.promo_discount_amount or 0),
                        distance_at_usage=dist
                    )


                
                # order_total_price = float(order.get_total_price()) + order.delivery_fee + order.service_fee

                if request.data.get('payment_method') != 'wallet' and order.payment_method == 'wallet':
                    wallet, _ = Wallet.objects.get_or_create(user=user)
                    
                    if float(order_total_price) > float(wallet.balance):
                        raise ValueError('Insufficient balance. Please top up your wallet')
                    
                    # proceed the payment
                    wallet.balance -= order_total_price
                    wallet.save()
                    order.payment_status = 'paid'
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
                                    "order_details": OrderSerializer(order).data,
                                    'delivery_address': order.address,
                                    'created_at': order.created_at.isoformat(),
                                    'status': order.status,
                                }
                            }
                        )

                    except Exception as e:
                        print(e)

                    try:

                        send_order_payment_success_notification(
                            user=order.user,
                            order_id=str(order.id),
                            amount=str(order_total_price),
                        )
                    except Exception as e:
                        print(e)

                    # send other created push notification
                    try:
                        thread = notification_helper.send_to_user_async(
                            user=order.user,
                            title="Order Confirmed!",
                            body="Your order has been successfully placed. We’ll notify you when it’s on the way 🚚",
                            data={"event": "order_created", "order_id": order.id}
                        )
                    except Exception as e:
                        print(e)

                    try:
                        send_order_accepted_notification_customer(order)
                    except:pass

                    return success_response(
                        data=OrderSerializer(order).data,
                        message='Payment successful'
                    )
                else:
                    klass = PaystackManager()
                    order.payment_method = 'link'
                    order.save()

                    # if discount is applied, we need to pass the discounted amount to paystack
                    if promo_info["is_applied"]:
                        # check if the promo affects delivery fee or not, if it does, we need to subtract the discount amount from the delivery fee, if not, we need to subtract the discount amount from the total price
                        if promo_info.get("affects_delivery"):
                            order_total_price = float(order_total_price) - float(promo_info["discount_amount"]) 
                        else:
                            order_total_price = (
                                    float(order_total_price_without_delivery_fee) - float(promo_info["discount_amount"])
                                ) + float(delivery_fee)

                    return klass.initiate_payment(request, order_total_price, order,is_mobile=True, promo_info=promo_info)




                return success_response(
                    data=OrderSerializer(order).data,
                    message='Order created successfully (with variants)'
                )

        except ValidationError as ve:
            return bad_request_response(message=str(ve))
        except Exception as e:
            import traceback
            traceback_str = traceback.format_exc()
            print(traceback_str)
            return internal_server_error_response(message="An error occurred while creating your order.")

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
    permission_classes = [AllowAny]
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
        products = Product.objects.filter(parent=None,system_category__id=system_category_id)
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
    permission_classes = [AllowAny]
    queryset = Vendor.objects.all()

    def get_queryset(self,category_id=None):


        # category_id
        user = self.request.user

        query_location_latitude = self.request.GET.get('latitude')
        query_location_longitude = self.request.GET.get('longitude')

        is_marketplace = False

        if category_id:
            try:
                system_category = SystemCategory.objects.get(id=category_id)
                if system_category.name.lower() == 'marketplace':
                    is_marketplace = True
            except Exception as e:
                return Vendor.objects.none()

        if not is_marketplace:
            if not user or not isinstance(user, User):
                if any([not query_location_latitude, not query_location_latitude]):
                    return Vendor.objects.none()  

            print(f"User: {user}, query_location_latitude: {query_location_latitude}, query_location_longitude: {query_location_longitude}")
            if not query_location_latitude or not query_location_longitude:
                # user_address, _ = Address.objects.get_or_create(user=user)
                user_address = Address.objects.filter(user=user).order_by('-updated_at').first()
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
                location_latitude__isnull=False,
                location_longitude__isnull=False
            )



            if category_id:
                queryset = queryset.filter(category=system_category)



        else:
            marketplaces = MarketPlace.objects.all()

            if not marketplaces.exists():
                return Vendor.objects.none()

            vendor_ids = []

            for marketplace in marketplaces:
                vendor_ids.extend(
                    marketplace.vendors.values_list('id', flat=True)
                )

            queryset = Vendor.objects.filter(id__in=vendor_ids).distinct()

                
                # system_category = None
                
            
        

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

        if category_id:return queryset
            

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
                if dist is not None and dist <= vendor.delivery_radius_km:
                    vendors_within_5km.append(vendor)

        return vendors_within_5km


    

    @swagger_auto_schema(
        operation_description="Get vendors by system category",
        operation_summary="vendors by system category",
        responses={
            200: VendorSerializer,
        }
    )
    def get(self, request , system_category_id):

        queryset = self.get_queryset(category_id=system_category_id) 
        return paginate_success_response_with_serializer(
            request,
            self.serializer_class,
            queryset,
            page_size=int(request.GET.get('page_size',20))
        )
    
    
class HotPickProductsView(generics.GenericAPIView):
    permission_classes = [AllowAny]
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
        if request.user.is_authenticated:
            favorite_products = list(self.get_user_favorites(request.user))
        else:
            favorite_products = []

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
        if not favorites.exists():
            return []
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
    permission_classes = [AllowAny]

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
        serializer = self.serializer_class(product, context={'request': request, "is_vendor": request.user.is_authenticated and hasattr(request.user, 'vendor')})
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
    permission_classes = [AllowAny]

    
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
    permission_classes = [AllowAny]

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
    permission_classes = [AllowAny]

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
            data=self.serializer_class(self.get_queryset(), many=True).data
        )


class VendorIssueReportView(generics.GenericAPIView):
    serializer_class = VendorIssueReportSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        vendor_id = self.kwargs['vendor_id']
        try:
            vendor = Vendor.objects.get(id=vendor_id)
            return VendorIssueReporting.objects.filter(vendor=vendor)
        except Vendor.DoesNotExist:
            return VendorIssueReporting.objects.none()

    @swagger_auto_schema(
        operation_description="Submit a report for a specific vendor.",
        operation_summary="Report an issue for a vendor.",
        responses={
            200: VendorIssueReportSerializer(many=True),
            404: "Vendor not found.",
            401: "Authentication required."
        }
    )
    def post(self, request, *args, **kwargs):
        vendor_id = self.kwargs['vendor_id']
        try:
            vendor = Vendor.objects.get(id=vendor_id)
        except Vendor.DoesNotExist:
            return error_response("Vendor not found", status=404)
        data = request.data
        data['vendor'] = vendor.id
        data['user'] = request.user.id
        serializer = self.serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user, vendor=vendor)

        return success_response(
            message="Report successfully submiited."
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
    permission_classes = [AllowAny]
    def get(self,request,vendor_id):
        user = None
        if request.user.is_authenticated:
            user = request.user

        query_location_latitude = request.GET.get('latitude')
        query_location_longitude = request.GET.get('longitude')
        item_count = int(request.GET.get('item_count', 1))
        promo_code = request.GET.get('promo_code')
        order_value = float(request.GET.get('order_value', 0.0))


        try:
            vendor = Vendor.objects.get(id=vendor_id)
        except Vendor.DoesNotExist:
            return bad_request_response(message="Vendor not found")

        # Get user address
        
        location_latitude = None
        location_longitude = None 
        is_in_marketplace = MarketPlace.objects.filter(vendors=vendor).exists()

        
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
        


        if not is_in_marketplace:
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
            
            delivery_fee_info = calculate_delivery_fee(
                origin_lat=float(vendor.location_latitude),
                origin_lon=float(vendor.location_longitude),
                dest_lat=float(location_latitude),
                dest_lon=float(location_longitude),
                item_count=item_count,
                promo_code=promo_code,
                order_value=order_value,
                user_id=str(user.id) if user else None
            )
            delivery_fee = delivery_fee_info['total_fee']
            promo_details = delivery_fee_info.get('promo_details')
        else:
            delivery_fee_info = vendor.calculate_delivery_fee_by_vendor(
                item_count, 
                dest_lat=float(location_latitude), 
                dest_lon=float(location_longitude),
                user=user,
                promo_code=promo_code,
                order_value=order_value
            )
            delivery_fee = delivery_fee_info["total_fee"]
            promo_details = delivery_fee_info.get("promo_info",{})

        

        # create the delicery record here if needed
        record = DeliveryFee.objects.create(
            user=user,
            amount=float(delivery_fee),
            original_amount=float(delivery_fee_info.get('original_fee', delivery_fee)),
            vendor=vendor
        )
        return success_response(
            data={
                "delivery_fee": record.amount, 
                "id": str(record.id),
                "promo_details": promo_details
            },
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
        user = request.user
        items_data = request.data['items']
        vendor_id = serializer.validated_data['vendor_id']
        promo_code = request.data.get('promo_code')

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
                    if not main_product and item.get('variants') in [[],'',False,None]:
                        raise ValidationError(f"Product with ID {item['product']} not found.")

                    if main_product and main_product.vendor.id != vendor.id and item.get('variants') in [[],'',False,None]:
                        raise ValidationError(f"Product '{main_product.name}' does not belong to the selected vendor.")
                    

                    if item.get('variants'):
                        for variant in item['variants']:
                            variant_product = product_map.get(variant['product'])
                            if not variant_product:
                                raise ValidationError(f"Variant with ID {variant['product']} not found.")

                            if not variant_product.parent:
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
                            print(
                                f"Created item: {variant_product.name} x {variant['quantity']} @ {variant_product.price}"
                            )
                    else:
                        OrderItem.objects.create(
                            order=order,
                            product=main_product,
                            quantity=item['quantity'],
                            price=main_product.price
                        )
                        item_count += item['quantity']

                # Calculate delivery and finalize order
                # delivery_fee = calculate_delivery_fee(
                #     origin_lat=float(vendor.location_latitude),
                #     origin_lon=float(vendor.location_longitude),
                #     dest_lat=float(location_latitude),
                #     dest_lon=float(location_longitude),
                #     item_count=item_count
                # )['total_fee']

                delivery_fee_response = order.vendor.calculate_delivery_fee_by_vendor(
                    item_count, 
                    dest_lat=float(location_latitude), 
                    dest_lon=float(location_longitude),
                    user=user,
                    promo_code=promo_code,
                    order_value=float(order.total_price)
                )
                delivery_fee = delivery_fee_response["total_fee"]
                original_delivery_fee = delivery_fee_response["original_fee"]
                promo_info = delivery_fee_response["promo_info"]
                
                # Check for other benefits if it's an order-level promo
                from helpers.order_utils import apply_promo_code, get_distance_between_two_location
                
                dist = 0.0
                try:
                    dist = get_distance_between_two_location(
                        lat1=float(vendor.location_latitude),
                        lon1=float(vendor.location_longitude),
                        lat2=float(location_latitude),
                        lon2=float(location_longitude),
                    )
                except: pass

                # We call update_total_amount FIRST to get the subtotal
                order.update_total_amount()
                
                if promo_info["is_applied"]:
                    from product.promo_models import PromoCode
                    promo_obj = PromoCode.objects.filter(code__iexact=promo_info["code"]).first()
                    order.promo_code = promo_obj
                    order.promo_discount_amount = promo_info["discount_amount"]

                order.address = address
                order.location_latitude = location_latitude
                order.location_longitude = location_longitude
                order.note = request.data.get('note',request.data.get('notes'))
                order.delivery_fee = delivery_fee
                order.original_delivery_fee = original_delivery_fee
                from helpers.order_utils import calculate_rider_fare
                order.rider_earning = calculate_rider_fare(dist)
                order.save()

                if order.promo_code:
                    from product.promo_models import PromoUsage
                    PromoUsage.objects.create(
                        promo=order.promo_code,
                        user=user,
                        order=order,
                        discount_amount=order.promo_discount_amount or 0,
                        original_amount=float(order.total_price) + float(order.delivery_fee),
                        final_amount=float(order.total_price) + float(order.delivery_fee) - float(order.promo_discount_amount or 0),
                        distance_at_usage=dist
                    )

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
        delivery_fee_id = request.data.get('delivery_fee_id')
        promo_code = request.data.get('promo_code')

        user = request.user
        items_data = request.data['items']
        vendor_id = serializer.validated_data['vendor_id']

        # Get vendor
        try:
            vendor = Vendor.objects.get(id=vendor_id)
        except Vendor.DoesNotExist:
            return bad_request_response(message="Vendor not found")

        # Get user address
        delivery_fee = None
        if delivery_fee_id:
            delivery_fee_record = DeliveryFee.objects.get(id=delivery_fee_id, user=user, vendor=vendor, is_active=True )
            delivery_fee = delivery_fee_record.amount

        location_latitude = None
        location_longitude = None
        address = None
        
        if any([not query_location_latitude, not query_location_longitude]):
            user_address = Address.objects.filter(user=request.user,is_active=True).first()

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

        if distance_in_km is None or distance_in_km > vendor.delivery_radius_km:
            return bad_request_response(
                message="This vendor cannot deliver to your location (distance too far)."
            )

        product_ids = []
        for item in items_data:
            product_ids.append(item['product'])
            if item.get('variants') not in [[],'',False,None]:
                variants = item['variants']
                for variant in variants:
                    product_ids.append(variant['product'])
            # else:
            #     product_ids.append(item['product'])

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
                    if not main_product and item.get('variants') in [[],'',False,None]:
                        raise ValidationError(f"Product with ID {item['product']} not found.")

                    if main_product and main_product.vendor.id != vendor.id and item.get('variants') in [[],'',False,None]:
                        raise ValidationError(f"Product '{main_product.name}' does not belong to the selected vendor.")

                    if item.get('variants'):
                        for variant in item['variants']:
                            variant_product = product_map.get(variant['product'])
                            if not variant_product:
                                raise ValidationError(f"Variant with ID {variant['product']} not found.")

                            if not variant_product.parent:
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

                        if item.get('quantity') and item['quantity'] > 0:
                            OrderItem.objects.create(
                                order=order,
                                product=main_product,
                                quantity=item['quantity'],
                                price=main_product.price
                            )
                            item_count += item['quantity']
                    else:
                        OrderItem.objects.create(
                            order=order,
                            product=main_product,
                            quantity=item['quantity'],
                            price=main_product.price
                        )
                        item_count += item['quantity']

                # if vendor.is_marketplace:
                #     # get the marketplace the vendor belongs to
                #     try:
                #         marketplace = vendor.marketplace_set.first()
                #         delivery_fee = marketplace.delivery_fee
                #     except Exception as e:
                #         print(e)

                # else:
                #     # Calculate delivery and finalize order
                #     if not delivery_fee:
                #         delivery_fee = calculate_delivery_fee(
                #             origin_lat=float(vendor.location_latitude),
                #             origin_lon=float(vendor.location_longitude),
                #             dest_lat=float(location_latitude),
                #             dest_lon=float(location_longitude),
                #             item_count=item_count
                #         )['total_fee']

                delivery_fee_response = order.vendor.calculate_delivery_fee_by_vendor(
                    item_count, 
                    dest_lat=float(location_latitude), 
                    dest_lon=float(location_longitude),
                    user=user,
                    promo_code=promo_code,
                    order_value=float(order.total_price)
                )
                        
                delivery_fee = delivery_fee_response["total_fee"]
                original_delivery_fee = delivery_fee_response["original_fee"]
                promo_info = delivery_fee_response["promo_info"]

                order.update_total_amount()

                if promo_info["is_applied"]:
                    from product.promo_models import PromoCode
                    promo_obj = PromoCode.objects.filter(code__iexact=promo_info["code"]).first()
                    order.promo_code = promo_obj
                    order.promo_discount_amount = promo_info["discount_amount"]

                order.address = address
                order.location_latitude = location_latitude
                order.location_longitude = location_longitude
                order.payment_method = request.data.get('payment_method','wallet')
                order.note = request.data.get('note',request.data.get('notes'))
                order.delivery_fee = delivery_fee
                order.original_delivery_fee = original_delivery_fee
                from helpers.order_utils import calculate_rider_fare
                order.rider_earning = calculate_rider_fare(distance_in_km)
                order.save()


                order_total_price = float(order.get_total_price()) + order.delivery_fee 

                if order.promo_code:
                    from product.promo_models import PromoUsage
                    PromoUsage.objects.create(
                        promo=order.promo_code,
                        user=user,
                        order=order,
                        discount_amount=order.promo_discount_amount or 0,
                        original_amount=order_total_price,
                        final_amount=order_total_price - float(order.promo_discount_amount or 0),
                        distance_at_usage=distance_in_km
                    )

                 
                # order_total_price = float(order.get_total_price()) + order.delivery_fee + order.service_fee

                if request.data.get('payment_method') != 'wallet' and order.payment_method == 'wallet':
                    wallet, _ = Wallet.objects.get_or_create(user=user)
                    
                    if float(order_total_price) > float(wallet.balance):
                        raise ValueError('Insufficient balance. Please top up your wallet')
                    
                    # proceed the payment
                    wallet.balance -= order_total_price
                    wallet.save()
                    order.payment_status = 'paid'
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
                                    "order_details": OrderSerializer(order).data,
                                    'delivery_address': order.address,
                                    'created_at': order.created_at.isoformat(),
                                    'status': order.status,
                                }
                            }
                        )

                    except Exception as e:
                        print(e)

                    try:

                        send_order_payment_success_notification(
                            user=order.user,
                            order_id=str(order.id),
                            amount=str(order.total_price),
                        )
                    except Exception as e:
                        print(e)

                    # send other created push notification
                    try:
                        thread = notification_helper.send_to_user_async(
                            user=order.user,
                            title="Order Confirmed!",
                            body="Your order has been successfully placed. We’ll notify you when it’s on the way 🚚",
                            data={"event": "order_created", "order_id": order.id}
                        )
                    except Exception as e:
                        print(e)

                    try:
                        send_order_accepted_notification_customer(order)
                    except:pass

                    respnse_data = OrderSerializer(order).data
                    respnse_data['promo_info'] = promo_info
                    return success_response(
                        data=respnse_data,
                        message='Payment successful'
                    )
                else:
                    klass = PaystackManager()
                    order.payment_method = 'link'
                    order.save()
                    return klass.initiate_payment(request, order_total_price, order,is_mobile=True, promo_info=promo_info)


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
    lookup_field = "pk"

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

    def get_object(self):
        try:
            # Restrict to current user's orders only (optional)
            return self.get_queryset().get(pk=self.kwargs.get(self.lookup_field))
        except Order.DoesNotExist:
            raise NotFound("Order not found.")
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['include_delivery_info'] = True
        # context['requested_by'] = self.request.user.username
        return context
    
    def get_queryset(self):
        """Only return orders belonging to the authenticated user."""
        return Order.objects.all()


class UserFavoriteListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FavoriteVendorSerializer

    @swagger_auto_schema(
        operation_description="List all products in the user's favorites.",
        operation_summary="Retrieve products from the user's favorites.",
        responses={
            200: FavoriteVendorSerializer(many=True),
            401: "Unauthorized",
        }
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    def get_queryset(self):
        return UserFavoriteVendor.objects.filter(user=self.request.user).order_by('-created_at')
    

    def get(self, request,*args, **kwargs):
        limit = int(request.GET.get('limit', 10))

        
        # Limit the results to 'limit' number of vendors
        # return success_response(data=self.serializer_class(list(combined_vendors)[:limit], many=True).data)
        return paginate_success_response_with_serializer(
            request,
            self.serializer_class,
            self.get_queryset(),
            limit,
        )


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

                promo_code = request.data.get('promo_code')
                
                # Calculate delivery and finalize order
                delivery_fee_info = calculate_delivery_fee(
                    origin_lat=vendor.location_latitude,
                    origin_lon=vendor.location_longitude,
                    dest_lat=location_latitude,
                    dest_lon=location_longitude,
                    item_count=item_count,
                    user_id=str(user.id) if user else None,
                    promo_code=promo_code,
                    order_value=float(order.total_price)
                )
                delivery_fee = delivery_fee_info['total_fee']
                original_delivery_fee = delivery_fee_info['original_fee']
                promo_info = delivery_fee_info.get('promo_info', {"is_applied": False, "discount_amount": 0})
                
                if promo_info["is_applied"]:
                    from product.promo_models import PromoCode
                    promo_obj = PromoCode.objects.filter(code__iexact=promo_info["code"]).first()
                    order.promo_code = promo_obj
                    order.promo_discount_amount = promo_info["discount_amount"]

                order.address = address
                order.location_latitude = location_latitude
                order.location_longitude = location_longitude
                order.delivery_fee = delivery_fee
                order.original_delivery_fee = original_delivery_fee
                
                from helpers.order_utils import get_distance_between_two_location, calculate_rider_fare
                dist = 0.0
                try:
                    dist = get_distance_between_two_location(
                        lat1=float(vendor.location_latitude),
                        lon1=float(vendor.location_longitude),
                        lat2=float(location_latitude),
                        lon2=float(location_longitude),
                    )
                except: pass
                order.rider_earning = calculate_rider_fare(dist)
                
                order.save()

                if order.promo_code:
                    from product.promo_models import PromoUsage
                    PromoUsage.objects.update_or_create(
                        order=order,
                        defaults={
                            'promo': order.promo_code,
                            'user': user,
                            'discount_amount': order.promo_discount_amount or 0,
                            'original_amount': float(order.total_price) + float(order.delivery_fee),
                            'final_amount': float(order.total_price) + float(order.delivery_fee) - float(order.promo_discount_amount or 0),
                            'distance_at_usage': dist
                        }
                    )

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


class PromoCodeListView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = PromoCodeSerializer

    def get(self, request):
        active_promos = PromoCode.objects.filter(is_active=True)
        serializer = self.serializer_class(active_promos, many=True, context={'request': request})
        return success_response(data=serializer.data)

class PromoCodeDetailView(generics.GenericAPIView):
    """
    API endpoint to fetch and validate promo code details.
    Accepts optional query parameters for context-based validation:
    - order_value: Total order value
    - distance: Delivery distance in km
    - vendor_id: Vendor UUID
    """
    permission_classes = [AllowAny]
    
    @swagger_auto_schema(
        operation_description="Get promo code details and validation status. "
                            "Optionally provide order_value, distance, and vendor_id as query parameters for context-aware validation.",
        operation_summary="Retrieve promo code details",
        manual_parameters=[
            openapi.Parameter('code', openapi.IN_PATH, description="Promo code to validate", type=openapi.TYPE_STRING, required=True),
            openapi.Parameter('order_value', openapi.IN_QUERY, description="Total order value for validation (optional)", type=openapi.TYPE_NUMBER),
            openapi.Parameter('distance', openapi.IN_QUERY, description="Delivery distance in km (optional)", type=openapi.TYPE_NUMBER),
            openapi.Parameter('vendor_id', openapi.IN_QUERY, description="Vendor UUID (optional)", type=openapi.TYPE_STRING),
        ],
        responses={
            200: openapi.Response(
                description="Promo code details",
                examples={
                    "application/json": {
                        "status": "success",
                        "message": "Promo code details retrieved successfully",
                        "data": {
                            "id": "uuid-here",
                            "code": "SAVE20",
                            "promo_type": "percentage",
                            "promo_type_display": "Percentage Discount",
                            "value": "20.00",
                            "min_order_value": "50.00",
                            "max_discount": "100.00",
                            "max_distance_km": "10.00",
                            "start_date": "2026-01-01T00:00:00Z",
                            "end_date": "2026-12-31T23:59:59Z",
                            "is_active": True,
                            "is_automatic": False,
                            "is_valid": True,
                            "validation_message": "Valid"
                        }
                    }
                }
            ),
            404: openapi.Response(description="Promo code not found"),
        }
    )
    def get(self, request, code):
        """Fetch promo code details by code."""
        from product.promo_models import PromoCode
        from product.serializers import PromoCodeSerializer
        from django.utils import timezone
        
        try:
            # Find active promo code (case-insensitive)
            promo_code = PromoCode.objects.filter(
                code__iexact=code,
                is_active=True
            ).first()
            
            if not promo_code:
                return bad_request_response(
                    message="Promo code not found or is inactive"
                )
            
            # Serialize with context for validation
            serializer = PromoCodeSerializer(promo_code, context={'request': request})
            
            return success_response(
                message="Promo code details retrieved successfully",
                data=serializer.data
            )
            
        except Exception as e:
            traceback_str = traceback.format_exc()
            print(traceback_str)
            return internal_server_error_response(
                message="An error occurred while retrieving the promo code"
            )
