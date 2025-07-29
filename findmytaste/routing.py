# Using Django Channels for real-time tracking updates

# settings.py additions

# routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/tracking/(?P<order_id>[\w-]+)/$', consumers.OrderTrackingConsumer.as_asgi()),
    re_path(r'ws/delivery/(?P<order_id>[0-9a-f-]+)/$', consumers.DeliveryTrackingConsumer.as_asgi()),
]




