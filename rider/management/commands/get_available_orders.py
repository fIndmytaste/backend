from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from account.models import Rider
from helpers.order_utils import get_distance_between_two_location
from product.models import Order

class Command(BaseCommand):
    help = 'Get available orders for a rider (by email) and print their details.'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='Email of the rider user')
        parser.add_argument('--latitude', type=float, help='Current latitude of the rider (optional)')
        parser.add_argument('--longitude', type=float, help='Current longitude of the rider (optional)')

    def handle(self, *args, **options):
        email = options['email']
        latitude = options.get('latitude')
        longitude = options.get('longitude')
        User = get_user_model()
        try:
            user = User.objects.get(email=email)
            rider = Rider.objects.get(user=user)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User with email {email} does not exist.'))
            return
        except Rider.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Rider for user {email} does not exist.'))
            return

        # Determine which location to use
        if latitude is None or longitude is None:
            rider_lat = rider.current_latitude
            rider_lon = rider.current_longitude
            # if not rider_lat or not rider_lon:
            #     rider_lat = rider.location_latitude
            #     rider_lon = rider.location_longitude
        else:
            rider_lat = latitude
            rider_lon = longitude

        if not rider_lat or not rider_lon:
            self.stdout.write(self.style.ERROR('Rider location not available. Please update your current location or address.'))
            return
        


        latest_order = Order.objects.order_by('-created_at').first()

        print(latest_order.status)
        print(latest_order.created_at)

        declined_order_ids = rider.declined_orders.values_list('order_id', flat=True)
        queryset = Order.objects.filter(
            rider=None,
            status__in=['looking_for_rider', 'awaiting_rider'],
        ).exclude(id__in=declined_order_ids)

        print("Rider current : ", rider.current_latitude, rider.current_longitude, rider.location_updated_at)


        # rider.location_latitude = '6.648296'
        # rider.location_longitude = rider_lon
        # rider.save()
        # Filter orders within 10km range
        nearby_orders = []
        for order in queryset:
            print(order.vendor.name, order.vendor.location_latitude, order.vendor.location_longitude)
            try:
                distance = get_distance_between_two_location(
                    lat1=float(rider_lat),
                    lon1=float(rider_lon),
                    lat2=float(order.vendor.location_latitude),
                    lon2=float(order.vendor.location_longitude)
                )
                if distance is not None and distance <= 10:
                    nearby_orders.append(order)
            except (ValueError, TypeError) as e:
                self.stdout.write(self.style.WARNING(f'Error calculating distance for order {order.id}: {e}'))
                continue

        if not nearby_orders:
            self.stdout.write(self.style.WARNING('No available orders found within 10km.'))
            return

        self.stdout.write(self.style.SUCCESS(f'Available orders for rider {email}:'))
        for order in nearby_orders:
            self.stdout.write(f'Order ID: {order.id}, Status: {order.status}, Location: ({order.location_latitude}, {order.location_longitude}), Created: {order.created_at}')
