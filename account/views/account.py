from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

# Endpoint for customers to delete their own account
from vendor.serializers import VendorSerializer

from helpers.services.firebase_service import FirebaseNotificationService
from rest_framework import generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from drf_yasg.utils import swagger_auto_schema  # Import the decorator
from drf_yasg import openapi  # Import for custom parameter and response types
from account.models import Address, FCMToken, Notification, Profile, PushNotificationLog, User, Vendor, VirtualAccount,Rider
from account.serializers import (
    BankAccountValidationSerializer,
    RiderAddressSerializer,
    VendorStatusUpdateSerializer, 
    VendorOpeningHoursSerializer,
    FCMTokenSerializer, InitiateWithdrawalSerializer, NotificationLogSerializer, NotificationSerializer, PasswordChangeSerializer, ProfileImageUploadSerializer, SendNotificationSerializer, UpdateBankAccountSerializer, UserAddressCreateSerializer, UserAddressSerializer, UserSerializer, VendorAddressSerializer, VirtualAccountSerializer)
from helpers.account_manager import AccountManager
from helpers.flutterwave import FlutterwaveManager
from helpers.paystack import PaystackManager
from helpers.response.response_format import bad_request_response, success_response, internal_server_error_response
from helpers.backblaze import upload_to_backblaze
from django.db import transaction
import logging,time



class VendorOpeningHoursUpdateView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = VendorOpeningHoursSerializer

    @swagger_auto_schema(
        operation_description="Update the vendor's opening and closing time.",
        operation_summary="Update vendor opening and closing time.",
        request_body=VendorOpeningHoursSerializer,
        responses={
            200: openapi.Response(description="Vendor opening/closing time successfully updated."),
            400: openapi.Response(description="Bad request or invalid time details."),
            401: openapi.Response(description="Authentication required."),
        }
    )
    def put(self, request):
        try:
            vendor = Vendor.objects.get(user=request.user)
        except Vendor.DoesNotExist:
            return bad_request_response(
                message="Vendor not found.",
                status_code=404
            )
        serializer = VendorOpeningHoursSerializer(vendor, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return success_response(
                message="Vendor opening/closing time updated successfully",
                data=serializer.data
            )
        return bad_request_response(message=serializer.errors)



# Endpoint for vendor to update all profile data
class VendorProfileUpdateView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = VendorSerializer

    def put(self, request):
        try:
            vendor = Vendor.objects.get(user=request.user)
        except Vendor.DoesNotExist:
            return bad_request_response(
                message="Vendor not found.",
                status_code=404
            )
        # Allow open_day and close_day to be updated
        serializer = VendorSerializer(vendor, data=request.data, partial=True, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return success_response(
                message="Vendor profile updated successfully",
                data=serializer.data
            )
        return bad_request_response(message=serializer.errors)
    
    
class DeleteAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, *args, **kwargs):
        user = request.user
        user.is_active = False  # Soft delete: deactivate account
        user.save()
        return success_response(message="Your account has been deactivated and scheduled for deletion.",status_code=status.HTTP_204_NO_CONTENT)
    
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


    # add delete account
    def delete(self, request, *args, **kwargs):
        """
        This endpoint deletes the authenticated user's account.
        """
        user = request.user
        user.delete()
        return success_response(message='Account deleted successfully')
        



class ProfileImageUploadView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProfileImageUploadSerializer

    @swagger_auto_schema(
        operation_description="Upload or update the authenticated user's profile image to Backblaze B2.",
        operation_summary="Upload profile image to Backblaze B2.",
        request_body=ProfileImageUploadSerializer,
        responses={
            200: openapi.Response(
                description="Profile image uploaded successfully",
                schema=ProfileImageUploadSerializer
            ),
            400: 'Bad Request - Invalid image or upload failed',
        }
    )
    def patch(self, request, *args, **kwargs):
        """
        This endpoint allows the authenticated user to upload or update their profile image to Backblaze B2.
        Uses database transactions to ensure rollback if upload fails.
        """
        user = request.user
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        profile_image = request.data.get('profile_image')
        thumbnail = request.data.get('thumbnail')
        
        if not profile_image and not thumbnail:
            return bad_request_response(message="No image file provided")
        
        # Store original profile image URL for rollback
        original_profile_image_url = user.profile_image_url
        
        try:
            with transaction.atomic():
                # Generate unique filename for the profile image
                import uuid
                from datetime import datetime
                
                if profile_image:
                    file_extension = profile_image.name.split('.')[-1].lower()
                    unique_filename = f"profile_images/user_{user.id}_{uuid.uuid4().hex[:8]}_{int(datetime.now().timestamp())}.{file_extension}"

                    
                    logging.info(f"Uploading profile image for user {user.id} to Backblaze B2: {unique_filename}")
                    
                    # Upload to Backblaze B2
                    upload_result = upload_to_backblaze(profile_image, unique_filename)
                    
                    # The upload_to_backblaze function returns the upload result directly on success
                    # or raises an exception on failure, so if we reach here, it was successful
                    download_url = upload_result.get('downloadUrl')
                    if not download_url:
                        logging.error(f"Backblaze upload succeeded but no download URL returned for user {user.id}")
                        return bad_request_response(message="Image upload failed - no download URL")
                    
                    # Update user's profile image URL
                    user.profile_image_url = download_url
                    user.save()
                    
                    logging.info(f"Profile image uploaded successfully for user {user.id}: {download_url}")
                    
                    # Return success response with updated data
                
                                
                if thumbnail:
                    file_extension = thumbnail.name.split('.')[-1].lower()
                    unique_filename = f"thumbnail_images/user_{user.id}_{uuid.uuid4().hex[:8]}_{int(datetime.now().timestamp())}.{file_extension}"

                    
                    logging.info(f"Uploading thumbnail for user {user.id} to Backblaze B2: {unique_filename}")
                    
                    # Upload to Backblaze B2
                    upload_result = upload_to_backblaze(thumbnail, unique_filename)
                    
                    # The upload_to_backblaze function returns the upload result directly on success
                    # or raises an exception on failure, so if we reach here, it was successful
                    download_url = upload_result.get('downloadUrl')
                    if not download_url:
                        logging.error(f"Backblaze upload succeeded but no download URL returned for user {user.id}")
                        return bad_request_response(message="Image upload failed - no download URL")
                    
                    vendor, _ = Vendor.objects.get_or_create(user=user)
                    # Update user's profile image URL
                    vendor.thumbnail_url = download_url
                    vendor.save()
                    
                    logging.info(f"Profile image uploaded successfully for user {user.id}: {download_url}")
                    
                    # Return success response with updated data
                
                
                response_serializer = self.serializer_class(user)
                return success_response(
                    message="Profile image uploaded successfully",
                    data=response_serializer.data
                )
                
        except Exception as e:
            # Log the error
            logging.error(f"Profile image upload failed for user {user.id}: {str(e)}")
            
            # Ensure user's profile image URL is restored (transaction should handle this automatically)
            user.refresh_from_db()
            if user.profile_image_url != original_profile_image_url:
                user.profile_image_url = original_profile_image_url
                user.save()
            
            return internal_server_error_response(
                message="Profile image upload failed. Please try again."
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
        return success_response(data=UserAddressSerializer(delivery_addresses, many=True).data)


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
        - location_latitude: The latitude coordinate.
        - location_longitude: The longitude coordinate.

        **Responses:**
        - 201: Successfully created the address.
        - 400: Bad request if the address already exists or input is invalid.
        """

        serializer = UserAddressCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Get validated data from serializer
        validated_data = serializer.validated_data

        # Deactivate all existing addresses for the user
        address_objects = Address.objects.filter(user=request.user)
        for address in address_objects:
            address.is_active = False
            address.is_primary = False
            address.save()

        # Create new address with validated data
        address_object = Address.objects.create(
            user=request.user,
            country=request.data.get("country"),
            state=request.data.get("state"),
            city=request.data.get("city"),
            location_latitude=str(request.data['location_latitude']),  # Convert to string for CharField
            location_longitude=str(request.data['location_longitude']),  # Convert to string for CharField
            is_primary=True,
            is_active=True,
            address=request.data.get("address"),
        )

        time.sleep(3)
        
        return success_response(UserAddressSerializer(address_object).data, status_code=201)



    def put(self, request):
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


        try:
            address_object = Address.objects.get(id=request.data.get('address_id'))
        except:
            return bad_request_response(
                message="address does not exist"
            )
        
        old_address_objects = Address.objects.filter(user=request.user)
        for address in old_address_objects:
            if address.id != address_object.id:
                address.is_active = False
                address.is_primary = False
                address.save()
        

        address_object.country = data.get('country',address_object.country)
        address_object.state = data.get('state',address_object.state)
        address_object.city = data.get('city',address_object.city)
        address_object.address = data.get('address',address_object.address)
        address_object.location_latitude = data.get('location_latitude',address_object.location_latitude)
        address_object.location_longitude = data.get('location_longitude',address_object.location_longitude)
        address_object.is_active = True
        address_object.is_primary = True
        address_object.save()


        time.sleep(3)


        
        return success_response(UserAddressSerializer(address_object).data)


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


class NotificationUnreadCountView(generics.GenericAPIView):
    """Returns the unread notification count for the authenticated user.

    Used by the mobile apps to render the navbar badge.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(user=request.user, read=False).count()
        return success_response(data={'unread_count': count})


class NotificationMarkReadView(generics.GenericAPIView):
    """Mark notifications as read.

    POST body (optional): {"ids": ["<uuid>", ...]}. If omitted, marks ALL
    notifications for the user as read.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ids = request.data.get('ids') if isinstance(request.data, dict) else None
        qs = Notification.objects.filter(user=request.user, read=False)
        if ids:
            qs = qs.filter(id__in=ids)
        updated = qs.update(read=True)
        return success_response(data={'marked_read': updated})


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

class GetAcceptedBanks(generics.GenericAPIView, AccountManager, FlutterwaveManager):
    permission_classes = []

    def get(self,request):
        klass = PaystackManager()
        success, banks = klass.banks()
        if not success:
            return bad_request_response(message=banks)
        return success_response(data=banks)

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
                bank_response['bank_name'],
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

        print(
            "Request data :: " ,  request.data
        )
        
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
            vendor.location_latitude = data.get('location_latitude', vendor.location_latitude)
            vendor.location_longitude = data.get('location_longitude', vendor.location_longitude)
            vendor.save()   

            print(
                "Vendor address updated: Latitude {}, Longitude {}".format(
                    vendor.location_latitude,
                    vendor.location_longitude
                )
            )

            return success_response(
                message="Vendor address updated successfully",
                data=serializer.data
                )
        
        return bad_request_response(message=serializer.errors)


class RiderAddressUpdateView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RiderAddressSerializer

    @swagger_auto_schema(
        operation_description="Update the rider's address.",
        operation_summary="Update rider address.",
        request_body=RiderAddressSerializer,
        responses={
            200: openapi.Response(description="Rider address successfully updated."),
            400: openapi.Response(description="Bad request or invalid address details."),
            401: openapi.Response(description="Authentication required."),
        }
    )
    def put(self, request):
        """
        Update rider address information.
        """
        try:
            rider = Rider.objects.get(user=request.user)
        except Rider.DoesNotExist:
            return bad_request_response(
                message="Rider not found.", 
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
        
        serializer = RiderAddressSerializer(rider, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return success_response(
                message="Rider address updated successfully",
                data=serializer.data
                )
        
        return bad_request_response(message=serializer.errors)


class VendorStatusUpdateView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = VendorStatusUpdateSerializer

    def patch(self, request):
        """
        Partially update the vendor's status or address information.
        """
        try:
            vendor = Vendor.objects.get(user=request.user)
        except Vendor.DoesNotExist:
            return bad_request_response(
                message="Vendor not found.",
                status_code=status.HTTP_404_NOT_FOUND
            )

        serializer = self.serializer_class(vendor, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return success_response(
            message="Vendor information updated successfully.",
            data=serializer.data
        )




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