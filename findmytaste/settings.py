import os
from pathlib import Path
from datetime import timedelta
import cloudinary
import dj_database_url
# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-&lhb+rrxl(*9*wzdo$nz&!!b$=q&hhzj3tqo(bkk994$(6ko4l'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ["*"]


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',


    # external apps
    'corsheaders',
    'rest_framework',
    'drf_yasg',
    'cloudinary',
    'cloudinary_storage',

    # local apps
    'account',
    'api',
    'product',
    'helpers',
    'vendor',
    'wallet',
    'rider',
    'admin_manager'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
]

ROOT_URLCONF = 'findmytaste.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'templates'), 
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'findmytaste.wsgi.application'



AUTH_USER_MODEL = 'account.User'

# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB'),
        'USER': os.getenv('POSTGRES_USER'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD'),
        'HOST': os.getenv('POSTGRES_HOST'),
        'PORT': os.getenv('POSTGRES_PORT'),
    }
}

# DATABASES = {
#     'default': dj_database_url.config()
# }


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = '/static/'

# Location to store static files (in development mode, static files will be stored in this folder)
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# List of directories to look for static files
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]


FLUTTERWAVE_AUTH_TOKEN=os.getenv('FLUTTERWAVE_AUTH_TOKEN')
PAYSTACK_SECRET_KEY=os.getenv('PAYSTACK_SECRET_KEY','sk_test_f2c4c12c87df60bc178d3be7a19ba4a975d17527')
# PAYSTACK_SECRET_KEY=os.getenv('PAYSTACK_SECRET_KEY','sk_test_f2c4c12c87df60bc178d3be7a19ba4a975d17527')

# MEDIA_URL = '/media/'
# MEDIA_ROOT = os.path.join(BASE_DIR, 'media')


# Cloudinary settings
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.getenv('CLOUDINARY_STORAGE_CLOUD_NAME'),
    'API_KEY': os.getenv('CLOUDINARY_STORAGE_API_KEY'),
    'API_SECRET': os.getenv('CLOUDINARY_STORAGE_API_SECRET'),
}

cloudinary.config(
  cloud_name = os.getenv('CLOUDINARY_STORAGE_CLOUD_NAME'),
  api_key = os.getenv('CLOUDINARY_STORAGE_API_KEY'),
  api_secret = os.getenv('CLOUDINARY_STORAGE_API_SECRET')
)

# print(CLOUDINARY_STORAGE)

DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

# Media files
MEDIA_URL = '/media/'

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CORS_ALLOW_ALL_ORIGINS = True


# JWT settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': 'your-secret-key',
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}


REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}



# # Email settings from environment variables
# EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
# EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
# EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
# EMAIL_USE_TLS = os.getenv('EMAIL_SECURE', 'false').lower() == 'false'
# EMAIL_USE_SSL = os.getenv('EMAIL_SECURE', 'false').lower() == 'true'
# EMAIL_HOST_USER = os.getenv('EMAIL_USER', 'programmerolakay@gmail.com')
# EMAIL_HOST_PASSWORD = os.getenv('EMAIL_PASSWORD', 'yhaxekkagbtdbxha')
# DEFAULT_FROM_EMAIL = f"{os.getenv('EMAIL_FROM_NAME', 'EMGS')} <{os.getenv('EMAIL_FROM_ADDRESS', 'programmerolakay@gmail.com')}>"

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp-relay.brevo.com'
EMAIL_PORT = 587
EMAIL_HOST_USER = '8f4753001@smtp-brevo.com' #  Your Brevo email address
EMAIL_HOST_PASSWORD = 'bzJOQGB1L7AkctX8' # Your Brevo SMTP key
EMAIL_USE_TLS = True



"""
INSTALLED_APPS = [
    # ... other apps
    'channels',
]

ASGI_APPLICATION = 'your_project.asgi.application'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
        # For production, use Redis:
        # 'BACKEND': 'channels_redis.core.RedisChannelLayer',
        # 'CONFIG': {
        #     "hosts": [('127.0.0.1', 6379)],
        # },
    },
}
"""

