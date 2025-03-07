from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema  # Import the decorator
from drf_yasg import openapi  # Import for custom parameter and response types
from account.models import Address, Notification, User
from account.serializers import NotificationSerializer, PasswordChangeSerializer, UserAddressCreateSerializer, UserAddressSerializer, UserSerializer
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


    def get(self,request,*args,**kwargs):
        """
        This endpoint allows the authenticated user to view their notifications.
        """
        return success_response(
            data=self.serializer_class(self.get_queryset(), many=True).data,
        )
        