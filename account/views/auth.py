from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from rest_framework import generics
from rest_framework.permissions import AllowAny
from account.models import User, VerificationCode
from account.serializers import LoginSerializer, PasswordResetConfirmSerializer, PasswordResetRequestSerializer, RegisterSerializer, RegisterVendorSerializer, UserSerializer
from helpers.response.response_format import bad_request_response, success_response
from helpers.tokens import TokenManager
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

class LoginAPIView(generics.GenericAPIView):
    """
    View to handle user login via email.
    """
    permission_classes = [AllowAny]  # This view can be accessed without authentication
    serializer_class = LoginSerializer

    @swagger_auto_schema(
        operation_description="Log in a user with email and password.",
        request_body=LoginSerializer,
        responses={}
    )
    def post(self, request, *args, **kwargs):
        """
        POST request to log in the user using email and password.

        **Request Body:**
        - identifier: Email or university ID of the user.
        - password: Password of the user.

        **Responses:**
        - 200: Successfully logged in, returning tokens and user data.
        - 400: Invalid credentials or inactive user.
        """
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid(raise_exception=True):
            identifier = serializer.validated_data['identifier']
            password = serializer.validated_data['password']

            # Try to authenticate the user with email or university_id
            user = authenticate(request, email=identifier, password=password)
            if user is not None and user.is_active:
                # User found and is active
                valid_user = User.objects.get(pk=user.id)
                tokens = TokenManager.get_tokens_for_user(user)
                response_data = {
                    "tokens" : tokens , 
                    'user' : UserSerializer(valid_user).data 
                }
                return success_response(message='Login successfully.', data=response_data)
            else:
                # Invalid credentials or inactive user
                return bad_request_response(message='Invalid credentials or user is not active.')

class RegisterAPIView(generics.GenericAPIView):
    """
    View to register a new user.
    """
    serializer_class = RegisterSerializer

    @swagger_auto_schema(
        operation_description="Register a new user and return the created user data and tokens.",
        request_body=RegisterSerializer,
        responses={}
    )
    def post(self, request, *args, **kwargs):
        """
        POST request to register a new user.

        **Request Body:**
        - username: The username of the user.
        - email: The email of the user.
        - password: The password for the new account.

        **Responses:**
        - 201: Successfully created the account with user data and tokens.
        - 400: Validation errors or bad input data.
        """
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        valid_user = User.objects.get(pk=user.id)
        tokens = TokenManager.get_tokens_for_user(user)
        response_data = {
            "tokens" : tokens , 
            'user' : UserSerializer(valid_user).data 
        }
        return success_response(
            data=response_data,
            message='Account created successfully.'
        )

class RegisterVendorAPIView(generics.GenericAPIView):
    """
    View to register a new vendor.
    """
    serializer_class = RegisterVendorSerializer

    @swagger_auto_schema(
        operation_description="Register a new vendor and return the created user data and tokens.",
        request_body=RegisterVendorSerializer,
        responses={}
    )
    def post(self, request, *args, **kwargs):
        """
        POST request to register a new vendor.

        **Request Body:**
        - username: The vendor's username.
        - email: The vendor's email.
        - password: The vendor's password.

        **Responses:**
        - 201: Successfully created the vendor account with user data and tokens.
        - 400: Validation errors or bad input data.
        """
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        valid_user = User.objects.get(pk=user.id)
        tokens = TokenManager.get_tokens_for_user(user)
        response_data = {
            "tokens" : tokens , 
            'user' : UserSerializer(valid_user).data 
        }
        # generate six code 

        code_obj = VerificationCode.objects.create(
            user=valid_user,
            verification_type='email'
        )

        print(code_obj.code)
        print(code_obj.code)
        print(code_obj.code)
        # send verification code to email
        return success_response(
            data=response_data,
            message='Account created successfully.'
        )



class PasswordResetConfirmView(generics.GenericAPIView):
    """
    View to confirm the password reset using the provided token.
    """
    serializer_class = PasswordResetConfirmSerializer

    @swagger_auto_schema(
        operation_description="Reset the user's password using the token sent via email.",
        request_body=PasswordResetConfirmSerializer,
        responses={
            200: 'Password successfully reset.',
            400: 'Invalid token or user ID.'
        }
    )
    def post(self, request, uidb64, token, *args, **kwargs):
        """
        POST request to confirm the password reset.

        **Request Body:**
        - new_password: The new password for the user.

        **Responses:**
        - 200: Successfully reset the password.
        - 400: Invalid or expired token.
        """
        try:
            # Decode the user ID from the URL
            uid = urlsafe_base64_decode(uidb64).decode()
            user = get_user_model().objects.get(pk=uid)
        except (ValueError, TypeError, get_user_model().DoesNotExist):
            return bad_request_response(message="Invalid token or user ID.")

        # Validate the token
        if not default_token_generator.check_token(user, token):
            return bad_request_response(message="Invalid or expired token.")

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_password = serializer.validated_data['new_password']

        # Set the new password and save
        user.set_password(new_password)
        user.save()

        return success_response(message="Password successfully reset.")

class PasswordResetRequestView(generics.GenericAPIView):
    """
    View to handle the password reset request.
    """
    serializer_class = PasswordResetRequestSerializer

    @swagger_auto_schema(
        operation_description="Send a password reset link to the user's email.",
        request_body=PasswordResetRequestSerializer,
        responses={
            200: 'Password reset email sent.',
            400: 'User with this email does not exist.'
        }
    )
    def post(self, request, *args, **kwargs):
        """
        POST request to initiate the password reset process.

        **Request Body:**
        - email: The email of the user requesting the password reset.

        **Responses:**
        - 200: Successfully sent the password reset email.
        - 400: User with this email does not exist.
        """
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        user_model = get_user_model()

        try:
            user = user_model.objects.get(email=email)
        except user_model.DoesNotExist:
            return bad_request_response(message="User with this email does not exist.")

        # Generate password reset token and uid
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(user.pk.encode())

        # Construct the reset link
        reset_link = f"/password-reset/{uid}/{token}/"

        # Send the email with the reset link
        subject = "Password Reset Request"

        return success_response(message="Password reset email sent.")


