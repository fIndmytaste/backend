from django.urls import path
from . import notification_views

app_name = 'notifications'

urlpatterns = [
    # Send notification
    path('send/', notification_views.send_notification, name='send_notification'),
    
    # Get templates
    path('templates/', notification_views.get_notification_templates, name='get_templates'),
    
    # Get specific template info
    path('templates/<str:user_type>/<str:category>/<str:template_key>/', 
         notification_views.get_template_info, name='get_template_info'),
    
    # Preview notification
    path('preview/', notification_views.preview_notification, name='preview_notification'),
]