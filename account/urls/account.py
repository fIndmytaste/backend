from django.urls import path
from account.views.account import (
    MyVirtualAccountNumberView, NotificationListView, PasswordChangeView, ProfileImageUploadView, 
    UserAddressUpdateView, UserDetailView,
    UpdateVenderBankAccount, ValidateBankAccountNumber, VendorAddressUpdateView
)


urlpatterns = [ 
    path('', UserDetailView.as_view(), name='user-profile'),
    path('profile/', UserDetailView.as_view(), name='current-user-profile'),
    path('profile-image-upload', ProfileImageUploadView.as_view(), name='ProfileImageUploadView'),
    path('delivery-address', UserAddressUpdateView.as_view(), name='current-user-address'),
    path('password/change/', PasswordChangeView.as_view(), name='password-change'),
    path('notification', NotificationListView.as_view(), name='password-change'),
    path('bank-account', UpdateVenderBankAccount.as_view(), name='password-change'),
    path('virtual-account', MyVirtualAccountNumberView.as_view(), name='virtual-account'),
    path('vendor/update-address/', VendorAddressUpdateView.as_view(), name='update-vendor-address'),
    path('rider/update-address/', VendorAddressUpdateView.as_view(), name='update-vendor-address'),
]
