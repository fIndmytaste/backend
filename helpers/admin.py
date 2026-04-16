from django.contrib import admin
from django.forms import JSONField
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import DeliveryConfiguration


@admin.register(DeliveryConfiguration)
class DeliveryConfigurationAdmin(admin.ModelAdmin):
    list_display = ['key', 'category', 'data_type', 'formatted_value', 'is_active', 'updated_at']
    list_filter = ['category', 'data_type', 'is_active', 'created_at']
    search_fields = ['key', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('key', 'category', 'description')
        }),
        ('Value Configuration', {
            'fields': ('data_type', 'value', 'default_value')
        }),
        ('Validation & Constraints', {
            'fields': ('min_value', 'max_value', 'is_active'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def formatted_value(self, obj):
        """Display formatted value based on data type."""
        try:
            value = obj.get_typed_value()
            if obj.data_type == 'json':
                # Pretty print JSON
                import json
                return format_html('<pre>{}</pre>', json.dumps(value, indent=2))
            elif obj.data_type == 'boolean':
                return format_html(
                    '<span style="color: {};">{}</span>',
                    'green' if value else 'red',
                    '✓ True' if value else '✗ False'
                )
            elif obj.data_type in ['integer', 'float']:
                return format_html('<strong>{}</strong>', value)
            else:
                return str(value)[:100] + ('...' if len(str(value)) > 100 else '')
        except Exception as e:
            return format_html('<span style="color: red;">Error: {}</span>', str(e))
    
    formatted_value.short_description = 'Current Value'
    formatted_value.allow_tags = True
    
    def get_queryset(self, request):
        """Order by category and key for better organization."""
        return super().get_queryset(request).order_by('category', 'key')
    
    class Media:
        css = {
            'all': ('admin/css/delivery_config.css',)
        }
        js = ('admin/js/delivery_config.js',)


# Custom admin actions
def reset_to_default(modeladmin, request, queryset):
    """Reset selected configurations to their default values."""
    count = 0
    for config in queryset:
        if config.default_value:
            config.value = config.default_value
            config.save()
            count += 1
    
    modeladmin.message_user(
        request,
        f'Successfully reset {count} configuration(s) to default values.'
    )

reset_to_default.short_description = "Reset selected configurations to default values"


def duplicate_configuration(modeladmin, request, queryset):
    """Duplicate selected configurations with '_copy' suffix."""
    count = 0
    for config in queryset:
        new_config = DeliveryConfiguration(
            key=f"{config.key}_copy",
            category=config.category,
            data_type=config.data_type,
            value=config.value,
            default_value=config.default_value,
            description=f"Copy of {config.description}",
            min_value=config.min_value,
            max_value=config.max_value,
            is_active=False  # Start as inactive
        )
        new_config.save()
        count += 1
    
    modeladmin.message_user(
        request,
        f'Successfully duplicated {count} configuration(s).'
    )

duplicate_configuration.short_description = "Duplicate selected configurations"

# Add custom actions to the admin
DeliveryConfigurationAdmin.actions = [reset_to_default, duplicate_configuration]
