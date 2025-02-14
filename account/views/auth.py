from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from rest_framework import generics
from rest_framework.permissions import AllowAny
from account.models import User
from account.serializers import LoginSerializer, PasswordResetConfirmSerializer, PasswordResetRequestSerializer, UserSerializer
from helpers.response.response_format import bad_request_response, success_response
from helpers.tokens import TokenManager







class LoginAPIView(generics.GenericAPIView):
    """
    View to handle user login via email or university ID.
    """
    permission_classes = [AllowAny]  # This view can be accessed without authentication
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        """
        POST request to log in the user. Accepts either email or university_id with password.
        """
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid(raise_exception=True):
            identifier = serializer.validated_data['identifier']
            password = serializer.validated_data['password']

            # Try to authenticate the user with email or university_id
            user = None
            if '@' in identifier:  # Email case
                user = authenticate(request, email=identifier, password=password)
            else:  # University ID case
                try:
                    user = User.objects.get(staffprofile__staff_id=identifier)
                    if user.check_password(password):
                        pass
                    else:
                        user = None
                except User.DoesNotExist:
                    user = None
            if user is not None and user.is_active:
                # User found and is active
                valid_user = User.objects.get(pk=user.id)
                tokens = TokenManager.get_tokens_for_user(user)
                response_data = {
                    "tokens" : tokens , 
                    'user' : UserSerializer(valid_user).data 
                }
                return success_response(message='Login successfully.',data=response_data)
            else:
                # Invalid credentials or inactive user
                return bad_request_response(message='Invalid credentials or user is not active.')




class PasswordResetConfirmView(generics.GenericAPIView):
    serializer_class = PasswordResetConfirmSerializer

    def post(self, request, uidb64, token, *args, **kwargs):
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

        return success_response(message= "Password successfully reset.")
    


class PasswordResetRequestView(generics.GenericAPIView):
    serializer_class = PasswordResetRequestSerializer

    def post(self, request, *args, **kwargs):
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
        # reset_link = f"{settings.FRONTEND_URL}/password-reset/{uid}/{token}/"

        # Send the email with the reset link
        subject = "Password Reset Request"
        

        return success_response(message= "Password reset email sent.")
    
