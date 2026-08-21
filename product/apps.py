from django.apps import AppConfig


class ProductConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'product'

    def ready(self):
        # Registers the vendor new-order alert.
        from product import signals  # noqa: F401
