from django.urls import path
from account.views.account import (
    MyVirtualAccountNumberView, NotificationListView,
    NotificationUnreadCountView, NotificationMarkReadView,
    PasswordChangeView, ProfileImageUploadView, RegisterFCMTokenView,
    UserAddressUpdateView, UserDetailView, RiderAddressUpdateView,
    UpdateVenderBankAccount, GetAcceptedBanks, VendorOpeningHoursUpdateView, VendorProfileUpdateView, VendorStatusUpdateView,
    VendorAddressUpdateView, AccountWithdrawalInitiate, unregister_fcm_token, DeleteAccountView,
    TawkSupportLoginView
)


urlpatterns = [ 
    path('', UserDetailView.as_view(), name='user-profile'),
    path('profile/', UserDetailView.as_view(), name='current-user-profile'),
    path('profile-image-upload/', ProfileImageUploadView.as_view(), name='ProfileImageUploadView'),
    path('delivery-address/', UserAddressUpdateView.as_view(), name='current-user-address'),
    path('password/change/', PasswordChangeView.as_view(), name='password-change'),
    path('notification/', NotificationListView.as_view(), name='notification-list'),
    path('notification/unread-count/', NotificationUnreadCountView.as_view(), name='notification-unread-count'),
    path('notification/mark-read/', NotificationMarkReadView.as_view(), name='notification-mark-read'),
    path('bank-account/', UpdateVenderBankAccount.as_view(), name='update-vendor-bank-account'),
    path('banks/', GetAcceptedBanks.as_view(), name='get-accepted-banks'),
    path('virtual-account/', MyVirtualAccountNumberView.as_view(), name='virtual-account'),
    path('vendor/update-address/', VendorAddressUpdateView.as_view(), name='update-vendor-address'),
    path('vendor/update-hours/', VendorOpeningHoursUpdateView.as_view(), name='update-vendor-hours'),
    path('vendor/update-profile/', VendorProfileUpdateView.as_view(), name='update-vendor-profile'),
    path('vendor/update-status/', VendorStatusUpdateView.as_view(), name='update-vendor-status'),
    path('rider/update-address/', RiderAddressUpdateView.as_view(), name='update-rider-address'),
    path('initiate-withdrawal/', AccountWithdrawalInitiate.as_view(), name='initiate-withdrawal'),
    path('fcm/register/', RegisterFCMTokenView.as_view(), name='register_fcm_token'),
    path('fcm/unregister/', unregister_fcm_token, name='unregister_fcm_token'),
    path('delete/', DeleteAccountView.as_view(), name='delete-account'),
    path('support/tawk-login/', TawkSupportLoginView.as_view(), name='tawk-support-login'),
]
