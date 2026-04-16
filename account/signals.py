from django.db.models.signals import post_save
from django.dispatch import receiver

from wallet.models import Wallet
from .models import User, Profile

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Creates a Profile instance for every new User.
    """
    if created:
        Profile.objects.create(user=instance)
        Wallet.objects.create(user=instance)
