from django.contrib import admin
from .models import SystemCategory, VendorCategory, Product, ProductImage, Order,OrderItem,Rating,Favorite,ProductView
# Register your models here.


admin.site.register(SystemCategory)
admin.site.register(VendorCategory)
admin.site.register(Product)
admin.site.register(ProductImage)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(Rating)
admin.site.register(Favorite)
admin.site.register(ProductView)