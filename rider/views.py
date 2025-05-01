# views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from account.models import Rider
from product.models import Order
from .serializers import (
    OrderSerializer, 
    RiderSerializer, 
    DeliveryTrackingSerializer,
    RiderLocationUpdateSerializer
)

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        # Filter orders based on user role
        if hasattr(user, 'rider'):
            # If user is a rider, show assigned orders
            return Order.objects.filter(rider=user.rider)
        elif hasattr(user, 'vendor'):
            # If user is a vendor, show their orders
            return Order.objects.filter(vendor=user.vendor)
        else:
            # Regular customer sees their own orders
            return Order.objects.filter(user=user)
    
    @action(detail=True, methods=['post'])
    def assign_rider(self, request, pk=None):
        order = self.get_object()
        rider_id = request.data.get('rider_id')
        
        if not rider_id:
            return Response({'error': 'Rider ID is required'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            rider = Rider.objects.get(id=rider_id)
            order.assign_rider(rider)
            return Response({'status': 'Rider assigned successfully'})
        except Rider.DoesNotExist:
            return Response({'error': 'Rider not found'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=True, methods=['get'])
    def tracking(self, request, pk=None):
        order = self.get_object()
        tracking_data = order.get_delivery_status()
        return Response(tracking_data)
    
    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        order = self.get_object()
        status = request.data.get('status')
        
        if not status:
            return Response({'error': 'Status is required'}, status=status.HTTP_400_BAD_REQUEST)
            
        # Map status strings to corresponding order methods
        status_methods = {
            'picked_up': order.mark_as_picked_up,
            'in_transit': order.mark_as_in_transit,
            'near_delivery': order.mark_as_near_delivery,
            'delivered': order.mark_as_delivered
        }
        
        if status in status_methods:
            status_methods[status]()
            return Response({'status': f'Order marked as {status}'})
        else:
            return Response({'error': 'Invalid status'}, status=status.HTTP_400_BAD_REQUEST)


class RiderViewSet(viewsets.ModelViewSet):
    queryset = Rider.objects.all()
    serializer_class = RiderSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        # If user is a rider, they can only see their own profile
        if hasattr(user, 'rider'):
            return Rider.objects.filter(user=user)
        
        # Admin or vendor can see all riders
        return Rider.objects.all()
    
    @action(detail=True, methods=['post'])
    def update_location(self, request, pk=None):
        rider = self.get_object()
        serializer = RiderLocationUpdateSerializer(data=request.data)
        
        if serializer.is_valid():
            latitude = serializer.validated_data['latitude']
            longitude = serializer.validated_data['longitude']
            
            rider.update_location(latitude, longitude)
            return Response({'status': 'Location updated successfully'})
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def toggle_online_status(self, request, pk=None):
        rider = self.get_object()
        go_online = request.data.get('online', False)
        
        if go_online:
            rider.go_online()
            return Response({'status': 'Rider is now online'})
        else:
            rider.go_offline()
            return Response({'status': 'Rider is now offline'})
    
    @action(detail=True, methods=['get'])
    def active_orders(self, request, pk=None):
        rider = self.get_object()
        active_orders = rider.orders.filter(
            status__in=['confirmed', 'ready_for_pickup', 'picked_up', 'in_transit', 'near_delivery']
        )
        serializer = OrderSerializer(active_orders, many=True)
        return Response(serializer.data)




