# consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from product.models import Order



class OrderTrackingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.order_id = self.scope['url_route']['kwargs']['order_id']
        self.room_group_name = f'order_tracking_{self.order_id}'
        
        # Accept connection without checking permissions
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial tracking data (if order exists)
        tracking_data = await self.get_tracking_data()
        if tracking_data:
            await self.send(text_data=json.dumps(tracking_data))
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        pass  # Not used here
    
    async def tracking_update(self, event):
        tracking_data = event['tracking_data']
        await self.send(text_data=json.dumps(tracking_data))
    
    @database_sync_to_async
    def get_tracking_data(self):
        try:
            order = Order.objects.get(id=self.order_id)
            return order.get_delivery_status()
        except Order.DoesNotExist:
            return None


class OrderTrackingConsumerOld(AsyncWebsocketConsumer):
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




class DeliveryTrackingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.order_id = self.scope['url_route']['kwargs']['order_id']
        self.room_group_name = f'delivery_{self.order_id}'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial order data
        order_data = await self.get_order_data()
        if order_data:
            await self.send(text_data=json.dumps({
                'type': 'order_update',
                'data': order_data
            }))

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        # Handle incoming WebSocket messages if needed
        pass

    # Receive message from room group
    async def delivery_update(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': event['type'],
            'data': event['data']
        }))

    async def rider_location_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'rider_location',
            'data': event['data']
        }))

    async def order_status_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'status_update',
            'data': event['data']
        }))

    @database_sync_to_async
    def get_order_data(self):
        try:
            from product.models import Order, DeliveryTracking
            order = Order.objects.select_related('rider', 'customer', 'vendor').get(id=self.order_id)
            
            # Get latest tracking data
            tracking = DeliveryTracking.objects.filter(order=order).last()
            
            return {
                'order_id': str(order.id),
                'status': order.status,
                'customer': {
                    'name': order.customer.full_name,
                    'phone': order.customer.phone_number,
                    'location': {
                        'latitude': float(order.delivery_latitude) if order.delivery_latitude else None,
                        'longitude': float(order.delivery_longitude) if order.delivery_longitude else None,
                        'address': order.delivery_address
                    }
                },
                'vendor': {
                    'name': order.vendor.name,
                    'location': {
                        'latitude': float(order.vendor.location_latitude) if order.vendor.location_latitude else None,
                        'longitude': float(order.vendor.location_longitude) if order.vendor.location_longitude else None,
                        'address': order.vendor.address
                    }
                },
                'rider': {
                    'name': order.rider.user.full_name if order.rider else None,
                    'phone': order.rider.user.phone_number if order.rider else None,
                    'current_location': {
                        'latitude': float(order.rider.current_latitude) if order.rider and order.rider.current_latitude else None,
                        'longitude': float(order.rider.current_longitude) if order.rider and order.rider.current_longitude else None,
                        'updated_at': order.rider.location_updated_at.isoformat() if order.rider and order.rider.location_updated_at else None
                    }
                } if order.rider else None,
                'tracking': {
                    'estimated_delivery_time': tracking.estimated_delivery_time.isoformat() if tracking and tracking.estimated_delivery_time else None,
                    'distance_to_customer': float(tracking.distance_to_customer) if tracking and tracking.distance_to_customer else None,
                } if tracking else None,
                'created_at': order.created_at.isoformat(),
                'updated_at': order.updated_at.isoformat()
            }
        except:
            return None

