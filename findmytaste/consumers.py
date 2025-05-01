# consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from product.models import Order


class OrderTrackingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.order_id = self.scope['url_route']['kwargs']['order_id']
        self.room_group_name = f'order_tracking_{self.order_id}'
        
        # Check if order exists and user has permission
        order_exists = await self.order_exists()
        if not order_exists:
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial tracking data
        tracking_data = await self.get_tracking_data()
        await self.send(text_data=json.dumps(tracking_data))
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    # Receive message from WebSocket (not used in this case)
    async def receive(self, text_data):
        pass
    
    # Receive message from room group
    async def tracking_update(self, event):
        tracking_data = event['tracking_data']
        
        # Send message to WebSocket
        await self.send(text_data=json.dumps(tracking_data))
    
    @database_sync_to_async
    def order_exists(self):
        try:
            user = self.scope['user']
            order = Order.objects.get(id=self.order_id)
            
            # Check permissions
            return (
                order.user == user or  # Customer who placed the order
                (hasattr(user, 'vendor') and order.vendor == user.vendor) or  # Vendor who received the order
                (hasattr(user, 'rider') and order.rider == user.rider)  # Rider assigned to the order
            )
        except Order.DoesNotExist:
            return False
    
    @database_sync_to_async
    def get_tracking_data(self):
        order = Order.objects.get(id=self.order_id)
        return order.get_delivery_status()
