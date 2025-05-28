from rest_framework import serializers


class RiderPerformanceMetricsSerializer(serializers.Serializer):
    average_delivery_time = serializers.CharField()
    on_time_deliveries = serializers.IntegerField()
    canceled_orders = serializers.IntegerField()
    overall_rating = serializers.DecimalField(max_digits=3, decimal_places=2)
    total_orders = serializers.IntegerField()
    completed_orders = serializers.IntegerField()
    completion_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    period = serializers.CharField()
