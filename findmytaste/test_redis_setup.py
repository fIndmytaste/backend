import os
import sys
import django

# Add project root to path and remove script directory to avoid naming conflicts (e.g., with celery.py)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Remove the internal 'findmytaste' directory from path if it was added by Python
INTERNAL_DIR = os.path.dirname(os.path.abspath(__file__))
if INTERNAL_DIR in sys.path:
    sys.path.remove(INTERNAL_DIR)

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'findmytaste.settings')
django.setup()

from django.core.cache import cache
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def test_redis_all():
    print("🚀 Starting Redis Integration Tests...\n")

    # 1. Test Cache
    print("--- Testing Django Cache ---")
    try:
        cache.set('redis_test_key', 'Hello from Redis!', timeout=30)
        value = cache.get('redis_test_key')
        if value == 'Hello from Redis!':
            print("✅ Cache: SUCCESS (Set/Get working)")
        else:
            print(f"❌ Cache: FAILED (Expected 'Hello from Redis!', got '{value}')")
    except Exception as e:
        print(f"❌ Cache: ERROR - {e}")

    # 2. Test Channels
    print("\n--- Testing Django Channels ---")
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.send)('test_channel', {'type': 'test.message', 'text': 'test'})
            print(f"✅ Channels: SUCCESS (Channel Layer: {channel_layer.__class__.__name__})")
        else:
            print("❌ Channels: FAILED (No channel layer configured)")
    except Exception as e:
        print(f"❌ Channels: ERROR - {e}")

    # 3. Test Celery
    print("\n--- Testing Celery Configuration ---")
    try:
        from findmytaste.celery import app as celery_app
        broker_url = celery_app.conf.broker_url
        print(f"📡 Celery Broker: {broker_url}")
        if 'redis://' in broker_url:
            print("✅ Celery: SUCCESS (Configured to use Redis)")
        else:
            print("❌ Celery: FAILED (Broker URL does not look like Redis)")
    except Exception as e:
        print(f"❌ Celery: ERROR - {e}")

    print("\n🏁 Tests Completed.")

if __name__ == "__main__":
    test_redis_all()
