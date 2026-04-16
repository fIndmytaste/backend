from django.contrib.auth.models import AnonymousUser
from channels.middleware import BaseMiddleware
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.db import close_old_connections
from channels.auth import AuthMiddlewareStack
from asgiref.sync import sync_to_async

class JWTAuthMiddleware(BaseMiddleware):
    """
    Custom middleware that takes JWT from Authorization header and authenticates the user.
    """
    async def __call__(self, scope, receive, send):
        headers = dict(scope["headers"])

        if b'authorization' in headers:
            print("++++"*10)
            auth_header = headers[b'authorization'].decode()
            if auth_header.startswith("Bearer "):
                token = auth_header.split("Bearer ")[1]
                jwt_auth = JWTAuthentication()
                try:
                    validated_token = await sync_to_async(jwt_auth.get_validated_token)(token)
                    validated_user = await sync_to_async(jwt_auth.get_user)(validated_token)
                    scope['user'] = validated_user
                except Exception as e:
                    print(e)
                    scope['user'] = AnonymousUser()
        else:
            scope['user'] = AnonymousUser()

        close_old_connections()
        return await super().__call__(scope, receive, send)




def JWTAuthMiddlewareStack(inner):
    print('Testing ======='*10)
    return JWTAuthMiddleware(AuthMiddlewareStack(inner))