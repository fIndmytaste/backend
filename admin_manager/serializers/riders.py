from rest_framework import serializers
from product.models import Order


class AdminRiderOrderSerializer(serializers.ModelSerializer):
    """Small, truthful order-history payload for the Rider Details table."""

    time_assigned = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'track_id', 'total_amount', 'status', 'delivery_status',
            'address', 'time_assigned', 'actual_pickup_time',
            'pickup_confirmed_at', 'actual_delivery_time', 'delivered_at',
            'created_at', 'updated_at',
        ]

    def get_time_assigned(self, obj):
        tracked_at = getattr(obj, 'time_assigned_at', None)
        if tracked_at:
            return tracked_at
        # Bulk admin assignment historically did not create a tracking row.
        # While the order remains assigned, updated_at is the assignment write.
        if obj.status == 'rider_assigned':
            return obj.updated_at
        return None


class RiderPerformanceMetricsSerializer(serializers.Serializer):
    average_delivery_time = serializers.CharField()
    on_time_deliveries = serializers.IntegerField()
    canceled_orders = serializers.IntegerField()
    overall_rating = serializers.DecimalField(max_digits=3, decimal_places=2)
    total_orders = serializers.IntegerField()
    completed_orders = serializers.IntegerField()
    completion_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    on_time_eligible_deliveries = serializers.IntegerField()
    reports_count = serializers.IntegerField()
    period = serializers.CharField()


class RiderEarningMetricsSerializer(serializers.Serializer):
    total_earnings = serializers.FloatField()
    total_payout = serializers.FloatField()
    balance = serializers.FloatField()
