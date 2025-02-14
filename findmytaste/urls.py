from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

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



urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('api.urls')),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0),
         name='schema-swagger-ui'),
    path('swagger.json', schema_view.without_ui(cache_timeout=0),name='schema-json'),
    path('', schema_view.with_ui('redoc', cache_timeout=0), name="read-doc"),
]
