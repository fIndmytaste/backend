from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema  # Import the decorator
from drf_yasg import openapi  # Import for custom parameter and response types
from account.models import Address, Notification, User, Vendor
from account.serializers import NotificationSerializer, PasswordChangeSerializer, UpdateBankAccountSerializer, UserAddressCreateSerializer, UserAddressSerializer, UserSerializer, VendorAddressSerializer
from helpers.account_manager import AccountManager
from helpers.flutterwave import FlutterwaveManager
from helpers.response.response_format import bad_request_response, success_response


class UserDetailView(generics.GenericAPIView):
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
        delivery_addresses = Address.objects.filter(user=request.user).order_by('created_at')
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
        serializer = self.serializer_class(user)
        serializer.is_valid(raise_exception=True)

        country = serializer.validated_data['country']
        state = serializer.validated_data['state']
        city = serializer.validated_data['city']
        address = serializer.validated_data['address']

        already_exist = Address.objects.filter(
            user=request.user,
            country=country,
            state=state,
            city=city,
            address=address,
        ).first()
        if already_exist:
            return bad_request_response(message="Address already exist")

        address_object = Address.objects.create(
            user=request.user,
            country=country,
            state=state,
            city=city,
            is_primary= not Address.objects.filter(user=request.user).exists(),
            address=address,
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
            bank_account = serialiser.validated_data['bank_account']
            bank_name = serialiser.validated_data['bank_name']
            bank_account_name = serialiser.validated_data['bank_account_name']
            
            # Validate bank details
            success, bank_response = self.validate_bank(bank_name)
            if not success:
                return bank_response
            
            # Resolve bank account details
            success, resolve_bank_account_response = self.resolve_bank_account(bank_account, bank_response['code'], bank_response['name'])
            if not success:
                return resolve_bank_account_response 
            
            # Add bank account to vendor
            success, response = self.add_bank_account(
                vendor,
                bank_response['code'],
                resolve_bank_account_response['account_number'],
                resolve_bank_account_response['account_name']
            )
            if success:
                return success_response(message=response)
            else:
                return bad_request_response(message=response)

        except Exception as e:
            return bad_request_response(message='An error occurred while updating the bank account details.')




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

