import string
import random
from django.db import migrations

def generate_referral_codes(apps, schema_editor):
    User = apps.get_model('account', 'User')
    for user in User.objects.all():
        if not user.referral_code:
            prefix = "FMT"
            if user.full_name:
                # Take first 4 characters of name, uppercase, remove non-alphanumeric
                clean_name = "".join(filter(str.isalnum, user.full_name)).upper()
                if clean_name:
                    prefix = clean_name[:4]
            elif user.email:
                # Fallback to email prefix
                clean_email = "".join(filter(str.isalnum, user.email.split('@')[0])).upper()
                if clean_email:
                    prefix = clean_email[:4]
            
            while True:
                suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
                code = f"{prefix}{suffix}"
                if not User.objects.filter(referral_code=code).exists():
                    user.referral_code = code
                    user.save()
                    break

class Migration(migrations.Migration):

    dependencies = [
        ("account", "0042_user_referral_code_user_referred_by"),
    ]

    operations = [
        migrations.RunPython(generate_referral_codes, reverse_code=migrations.RunPython.noop),
    ]
