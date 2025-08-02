from django.contrib import admin
from django.urls import path, include
from account.views.account import send_notification
from rest_framework.routers import DefaultRouter
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.conf import settings
from django.conf.urls.static import static
# findmytaste/views.py
import redis
from django.http import HttpResponse
# Create schema view
schema_view = get_schema_view(
   openapi.Info(
      title="FIND MY TASTE API",
      default_version='v1',
      description="Find My Taste API Documentation",
      terms_of_service="",
      contact=openapi.Contact(email="programmerolakay@gmail.com"),
      license=openapi.License(name="MIT"),
   ),
   public=True,  # Whether the schema is publicly accessible
)


def test_redis(request):
    try:
        r = redis.Redis(host="redis", port=6379, decode_responses=True)
        r.set("test_key", "Hello, Redis!")
        value = r.get("test_key")
        return HttpResponse(f"Redis test: {value}")
    except Exception as e:
        return HttpResponse(f"Redis connection failed: {str(e)}")

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('api.urls')),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0),
         name='schema-swagger-ui'),
    path('swagger.json', schema_view.without_ui(cache_timeout=0),name='schema-json'),
    path("test-redis/", test_redis, name="test_redis"),
    path('', schema_view.with_ui('redoc', cache_timeout=0), name="read-doc"),
    path('notifications/send/', send_notification, name='send_notification'),
    # path('notifications/history/', NotificationHistoryView.as_view(), name='notification_history'),
]


urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)



# from django.core.mail import send_mail

# res = send_mail(
#     "Subject here",
#     "Here is the message.",
#     "admin@findmytaste.com.ng",
#     ["programmerolakay@gmail.com","olakaycoder1@gmail.com","olanrewajutaiwo185@gmail.com"],
#     fail_silently=False,
# )

# print(res)

