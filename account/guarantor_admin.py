from django.contrib import admin
from .models import Guarantor

@admin.register(Guarantor)
class GuarantorAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone_number', 'relationship', 'rider', 'created_at')
    list_filter = ('relationship', 'created_at')
    search_fields = ('name', 'phone_number', 'rider__user__email')
    readonly_fields = ('created_at', 'updated_at')
