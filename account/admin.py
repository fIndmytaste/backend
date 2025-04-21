from django.contrib import admin
from .models import User, Rider, Vendor, VendorRating,VerificationCode, Profile, Notification
# Register your models here.


admin.site.register(User)
admin.site.register(Rider)
admin.site.register(Vendor)
admin.site.register(VendorRating)
admin.site.register(VerificationCode)
admin.site.register(Profile) 
admin.site.register(Notification)