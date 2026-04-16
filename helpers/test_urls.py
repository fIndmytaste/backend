# helpers/test_urls.py
from django.urls import path
from .test_views import (
    BackblazeTestUploadView,
    BackblazeTestDeleteView,
    BackblazeTestListView,
    BackblazeTestInfoView,
    BackblazeTestPageView,
    simple_backblaze_test
)

app_name = 'backblaze_test'

urlpatterns = [
    # HTML test page
    path('', BackblazeTestPageView.as_view(), name='test_page'),
    
    # API endpoints for testing
    path('upload/', BackblazeTestUploadView.as_view(), name='upload_test'),
    path('delete/', BackblazeTestDeleteView.as_view(), name='delete_test'),
    path('list/', BackblazeTestListView.as_view(), name='list_test'),
    path('info/', BackblazeTestInfoView.as_view(), name='info_test'),
    
    # Simple function-based test
    path('simple/', simple_backblaze_test, name='simple_test'),
]