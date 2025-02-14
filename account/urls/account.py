from django.urls import path
from account.views.account import PasswordChangeView, UserDetailView


urlpatterns = [ 
    path('', UserDetailView.as_view(), name='user-profile'),
    path('profile/', UserDetailView.as_view(), name='current-user-profile'),
    path('password/change/', PasswordChangeView.as_view(), name='password-change'),
]
