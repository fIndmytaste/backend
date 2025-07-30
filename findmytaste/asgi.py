import os

# Set DJANGO_SETTINGS_MODULE *before* anything else
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'findmytaste.settings')

import django
django.setup()

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import findmytaste.routing  # now safe to import

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            findmytaste.routing.websocket_urlpatterns
        )
    ),
})
