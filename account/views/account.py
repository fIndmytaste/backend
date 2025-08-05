from helpers.services.firebase_service import FirebaseNotificationService
from rest_framework import generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from drf_yasg.utils import swagger_auto_schema  # Import the decorator
from drf_yasg import openapi  # Import for custom parameter and response types
from account.models import Address, FCMToken, Notification, Profile, PushNotificationLog, User, Vendor, VirtualAccount
from account.serializers import BankAccountValidationSerializer, FCMTokenSerializer, InitiateWithdrawalSerializer, NotificationLogSerializer, NotificationSerializer, PasswordChangeSerializer, ProfileImageUploadSerializer, SendNotificationSerializer, UpdateBankAccountSerializer, UserAddressCreateSerializer, UserAddressSerializer, UserSerializer, VendorAddressSerializer, VirtualAccountSerializer
from helpers.account_manager import AccountManager
from helpers.flutterwave import FlutterwaveManager
from helpers.paystack import PaystackManager
from helpers.response.response_format import bad_request_response, success_response, internal_server_error_response


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    queryset = User.objects.all()
    serializer_class = UserSerializer

    @swagger_auto_schema(
        operation_description="Retrieve the details of the authenticated user.",
        operation_summary="Get details of the authenticated user.",
        responses={
            200: UserSerializer,
            400: 'Bad Request',
        }
    )
    def get(self, request, *args, **kwargs):
        """
        This endpoint retrieves the authenticated user's details.

        **Responses:**
        - 200: Successfully fetched user details.
        - 400: Bad request in case of any errors.
        """
        user = request.user
        serializer = UserSerializer(user)
        return success_response(serializer.data)
    

    def patch(self, request, *args, **kwargs):
        """
        This endpoint updates the authenticated user's details.
        """
        user = request.user
        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            email = request.data.get('email')
            if email:
                if User.objects.filter(email=email).exclude(id=user.id).exists():
                    return bad_request_response('Email already exists')
                
            serializer.save()
            return success_response(serializer.data)
        return bad_request_response(serializer.errors)
        



class ProfileImageUploadView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProfileImageUploadSerializer

    def patch(self, request, *args, **kwargs):
        """
        This endpoint allows the authenticated user to upload or update their profile image.
        """
        user = request.user
        serializer = self.serializer_class(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(
            message="Profile image updated successfully",
            data={
                "profile_image": serializer.data["profile_image"]
            }
        )
    
class UserAddressUpdateView(generics.GenericAPIView):
    serializer_class = UserAddressCreateSerializer
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get all the delivery addresses of the authenticated user.",
        operation_summary="Retrieve all delivery addresses of the authenticated user.",
        responses={
            200: openapi.Response(
                description="A list of user addresses",
                schema=UserAddressSerializer(many=True)
            ),
            400: 'Bad Request',
        }
    )
    def get(self, request):
        """
        This endpoint returns a list of all delivery addresses for the authenticated user.

        **Responses:**
        - 200: Successfully fetched the user's delivery addresses.
        - 400: Bad request in case of any errors.
        """
        delivery_addresses = Address.objects.filter(user=request.user).order_by('-created_at')

        all = Address.objects.filter().order_by('-created_at')
        return success_response(UserAddressSerializer(delivery_addresses, many=True).data)


    @swagger_auto_schema(
        operation_description="Create a new address for the authenticated user.",
        operation_summary="Create a new delivery address for the user.",
        request_body=UserAddressCreateSerializer,
        responses={
            201: openapi.Response(
                description="The newly created address.",
                schema=UserAddressSerializer
            ),
            400: 'Bad Request',
        }
    )
    def post(self, request, *args, **kwargs):
        """
        This endpoint allows the authenticated user to add a new address.

        **Request Body:**
        - country: The country of the address.
        - state: The state of the address.
        - city: The city of the address.
        - address: The detailed address.

        **Responses:**
        - 201: Successfully created the address.
        - 400: Bad request if the address already exists or input is invalid.
        """
        user = request.user

        serializer = UserAddressCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Validate coordinates before passing to serializer
        data = request.data
        
        # Validate location_latitude
        if 'location_latitude' in data and data['location_latitude'] is not None:
            try:
                lat = float(data['location_latitude'])
                if lat < -90 or lat > 90:
                    return bad_request_response(
                        message="Latitude must be between -90 and 90."
                    )
            except (ValueError, TypeError):
                return bad_request_response(
                    message="Latitude must be a valid number."
                )
        
        # Validate location_longitude
        if 'location_longitude' in data and data['location_longitude'] is not None:
            try:
                lng = float(data['location_longitude'])
                if lng < -180 or lng > 180:
                    return bad_request_response(
                        message="Longitude must be between -180 and 180."
                    )
            except (ValueError, TypeError):
                return bad_request_response(
                    message="Longitude must be a valid number."
                )


        address_object = Address.objects.create(
            user=request.user,
            country=data.get("country"),
            state=data.get("state"),
            city=data.get("city"),
            location_latitude=data['location_latitude'],
            location_longitude=data['location_longitude'] ,
            is_primary= not Address.objects.filter(user=request.user).exists(),
            address=data.get("address"),
        )
        
        return success_response(UserAddressSerializer(address_object).data, status_code=201)



    def put(self, request):

        user = request.user

        # Validate coordinates before passing to serializer
        data = request.data.copy()
        
        # Validate location_latitude
        if 'location_latitude' in data and data['location_latitude'] is not None:
            try:
                lat = float(data['location_latitude'])
                if lat < -90 or lat > 90:
                    return bad_request_response(
                        message="Latitude must be between -90 and 90."
                    )
            except (ValueError, TypeError):
                return bad_request_response(
                    message="Latitude must be a valid number."
                )
        
        # Validate location_longitude
        if 'location_longitude' in data and data['location_longitude'] is not None:
            try:
                lng = float(data['location_longitude'])
                if lng < -180 or lng > 180:
                    return bad_request_response(
                        message="Longitude must be between -180 and 180."
                    )
            except (ValueError, TypeError):
                return bad_request_response(
                    message="Longitude must be a valid number."
                )


        address_object = Address.objects.create(
            user=request.user,
            country=data.get("country"),
            state=data.get("state"),
            city=data.get("city"),
            location_latitude=data.get("location_latitude"),
            location_longitude=data.get("location_longitude"),
            is_primary= not Address.objects.filter(user=request.user).exists(),
            address=data.get("address"),
        )
        
        return success_response(UserAddressSerializer(address_object).data, status_code=201)


class PasswordChangeView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PasswordChangeSerializer

    @swagger_auto_schema(
        operation_description="Change the password for the authenticated user.",
        operation_summary="Change password for the authenticated user.",
        request_body=PasswordChangeSerializer,
        responses={
            200: openapi.Response(
                description="Password successfully changed"
            ),
            400: 'Bad Request',
        }
    )
    def post(self, request, *args, **kwargs):
        """
        This endpoint allows the authenticated user to change their password.

        **Request Body:**
        - current_password: The current password of the user.
        - new_password: The new password to be set.

        **Responses:**
        - 200: Successfully changed the password.
        - 400: Bad request if the current password is incorrect or input is invalid.
        """
        user = request.user
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        current_password = serializer.validated_data['current_password']
        new_password = serializer.validated_data['new_password']

        # Check if current password is correct
        if not user.check_password(current_password):
            return bad_request_response(message="Current password is incorrect.")

        # Set new password and save user
        user.set_password(new_password)
        user.save()

        return success_response(message="Password successfully changed.")


class NotificationListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    
    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by("-created_at")

    @swagger_auto_schema(
        operation_description="Retrieve a list of notifications for the authenticated user.",
        operation_summary="Get notifications for the authenticated user.",
        responses={
            200: openapi.Response(
                description="List of notifications successfully fetched.",
                schema=NotificationSerializer(many=True)
            ),
            401: openapi.Response(description="Authentication required."),
            400: openapi.Response(description="Bad request.")
        }
    )
    def get(self, request, *args, **kwargs):
        """
        This endpoint allows the authenticated user to view their notifications.

        **Response:**
        - A list of notifications with details including the message and creation timestamp.
        """
        return success_response(
            data=self.serializer_class(self.get_queryset(), many=True).data,
        )


class UpdateVenderBankAccount(generics.GenericAPIView, AccountManager, FlutterwaveManager):
    permission_classes = [IsAuthenticated]
    serializer_class = UpdateBankAccountSerializer

    @swagger_auto_schema(
        operation_description="Update the bank account details of the authenticated vendor.",
        operation_summary="Update vendor's bank account details.",
        request_body=UpdateBankAccountSerializer,
        responses={
            200: openapi.Response(description="Bank account successfully updated."),
            400: openapi.Response(description="Bad request or invalid bank details."),
            401: openapi.Response(description="Authentication required."),
        }
    )
    def put(self, request):
        """
        This endpoint allows the authenticated vendor to update their bank account details.

        **Request Body:**
        - `bank_account`: The bank account number.
        - `bank_name`: The name of the bank.
        - `bank_account_name`: The name on the bank account.

        **Response:**
        - `200`: Bank account details successfully updated.
        - `400`: Bad request if the input data is invalid or bank details cannot be resolved.
        """
        serialiser = UpdateBankAccountSerializer(data=request.data)
        serialiser.is_valid(raise_exception=True)
        try:
            user = User.objects.get(id=request.user.id)
            vendor = Vendor.objects.get(user=user)
            account_number = serialiser.validated_data['account_number']
            bank_code = serialiser.validated_data['bank_code']
            bank_name = serialiser.validated_data['bank_name']
            # bank_account_name = serialiser.validated_data['bank_account_name']

            klass = PaystackManager()

            # Validate bank details
            success, bank_response = klass.resolve_bank_account(
                account_number,
                bank_code,
            )

            if not success:
                return bad_request_response(message=bank_response)

            
            # Add bank account to vendor
            success, response = self.add_bank_account(
                vendor,
                bank_name,
                bank_response['account_number'],
                bank_response['account_name']
            )
            if success:
                return success_response(message=response)
            else:
                return bad_request_response(message=response)

        except Exception as e: 
            print(e)
            return bad_request_response(message='An error occurred while updating the bank account details.')


    def get(self,request):
        user = User.objects.get(id=request.user.id)
        vendor, _ = Vendor.objects.get_or_create(user=user)
        return success_response(
            data=dict(
                account_number=vendor.bank_account,
                bank_name=vendor.bank_name,
                bank_account_name=vendor.bank_account_name
            )
        )

class MyVirtualAccountNumberView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = VirtualAccountSerializer


    def get(self, request):
        user:User =  request.user
        try:
            virtual_account = VirtualAccount.objects.get(user=user)
            return success_response(
                data= self.serializer_class(virtual_account).data
            )
        except:pass
            
        
        if not user.full_name or user.full_name == '':
            return bad_request_response(message='Set your full name to proceed.')
        

        if not user.phone_number or user.phone_number == '':
            return bad_request_response(message='Set your phone number to proceed.')
        
        if not user.email or user.email == '':
            return bad_request_response(message='Set your email to proceed.')

        full_name = user.full_name
        full_name_split = full_name.split(' ')
        if len(full_name_split) > 1:
            first_name = full_name_split[0]
            last_name = full_name_split[1]
        else:
            first_name = full_name
            last_name = ''

        #  create a virtual customer for the user
        klass = PaystackManager()

        virtual_customer_success, virtual_customer_response = klass.create_virtual_customer(
            first_name,last_name,user.email,user.phone_number
        )
     
        if not virtual_customer_success:
            return internal_server_error_response(message='Unable to retrieve account at the moment')
        

        customer_ref = virtual_customer_response['customer_code']

        success, response_data = klass.create_virtual_account(customer_ref)

        if not success:return bad_request_response(message=response_data)

        # create the user record
        virtual_account = VirtualAccount.objects.create(
            user=request.user,
            account_number=response_data['account_number'],
            account_name=response_data['account_name'],
            bank_name=response_data['bank']['name'],
            provider_response=response_data,
            customer_reference=customer_ref
        )

        return success_response(data=self.serializer_class(virtual_account).data)







        return



class ValidateBankAccountNumber(generics.GenericAPIView):
    permission_classes = []
    serializer_class = BankAccountValidationSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data) 
        serializer.is_valid(raise_exception=True)

        klass = PaystackManager()
        
        success, response = klass.resolve_bank_account(
            request.data['account_number'],
            request.data['bank_code'],
        )
        return success_response(data=response) if success else bad_request_response(message=response)
        
           

class VendorAddressUpdateView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = VendorAddressSerializer

    @swagger_auto_schema(
        operation_description="Update the vendor's address.",
        operation_summary="Update vendor address.",
        request_body=VendorAddressSerializer,
        responses={
            200: openapi.Response(description="Vendor address successfully updated."),
            400: openapi.Response(description="Bad request or invalid address details."),
            401: openapi.Response(description="Authentication required."),
        }
    )
    def put(self, request):
        """
        Update vendor address information.
        """
        try:
            vendor = Vendor.objects.get(user=request.user)
        except Vendor.DoesNotExist:
            return bad_request_response(
                message="Vendor not found.", 
                status_code=404
            )
        
        # Validate coordinates before passing to serializer
        data = request.data.copy()
        
        # Validate location_latitude
        if 'location_latitude' in data and data['location_latitude'] is not None:
            try:
                lat = float(data['location_latitude'])
                if lat < -90 or lat > 90:
                    return bad_request_response(
                        message="Latitude must be between -90 and 90."
                    )
            except (ValueError, TypeError):
                return bad_request_response(
                    message="Latitude must be a valid number."
                )
        
        # Validate location_longitude
        if 'location_longitude' in data and data['location_longitude'] is not None:
            try:
                lng = float(data['location_longitude'])
                if lng < -180 or lng > 180:
                    return bad_request_response(
                        message="Longitude must be between -180 and 180."
                    )
            except (ValueError, TypeError):
                return bad_request_response(
                    message="Longitude must be a valid number."
                )
        
        serializer = VendorAddressSerializer(vendor, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return success_response(
                message="Vendor address updated successfully",
                data=serializer.data
                )
        
        return bad_request_response(message=serializer.errors)



class AccountWithdrawalInitiate(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class  = InitiateWithdrawalSerializer
    def post(self,request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        
        klass = PaystackManager()
        return klass.make_withdrawal(
            request,
            serializer.validated_data['amount'],

        )
    


class RegisterFCMTokenView(generics.CreateAPIView):
    serializer_class = FCMTokenSerializer
    permission_classes = [IsAuthenticated]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.save()

        return success_response(
            message='FCM token registered successfully',
            data=serializer.data,
            status_code=201
        ) 


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def send_notification(request):
    """Send push notification to users or topic"""
    
    serializer = SendNotificationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    data = serializer.validated_data

    results = None
    
    if data.get('topic'):
        # Send to topic
        result = FirebaseNotificationService.send_to_topic(
            topic=data['topic'],
            title=data['title'],
            body=data['body'],
            data=data.get('data'),
            image_url=data.get('image_url')
        )
    else:
        # Send to specific users
        user_ids = data['user_ids']
        results = []
        
        for user_id in user_ids:
            try:
                user = User.objects.get(id=user_id)
                result = FirebaseNotificationService.send_notification_to_user(
                    user=user,
                    title=data['title'],
                    body=data['body'],
                    data=data.get('data'),
                    image_url=data.get('image_url')
                )
                results.append({
                    'user_id': user_id,
                    'username': user.email,
                    **result
                })
            except User.DoesNotExist:
                results.append({
                    'user_id': user_id,
                    'success': False,
                    'error': 'User not found'
                })
        

    
    return success_response(data=result)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def unregister_fcm_token(request):
    """Unregister FCM token"""
    
    token = request.data.get('token')
    if not token:
        return bad_request_response(message='Token is required')
    
    deleted_count = FCMToken.objects.filter(
        user=request.user,
        token=token
    ).delete()[0]
    
    return success_response(message=f'Removed {deleted_count} token(s)')

class NotificationHistoryView(generics.ListAPIView):
    serializer_class = NotificationLogSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return PushNotificationLog.objects.filter(
            user=self.request.user
        ).order_by('-created_at')