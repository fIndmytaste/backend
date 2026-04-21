import os
from pathlib import Path
from datetime import timedelta
import cloudinary
from decouple import config
import firebase_admin
from firebase_admin import credentials

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
    'jazzmin',  # Jazzmin admin theme must come before 'django.contrib.admin'
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
    'channels',
    'channels_redis',

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
# Jazzmin admin theme configuration
JAZZMIN_SETTINGS = {
    "site_title": "FindMyTaste Admin",
    "site_header": "FindMyTaste Admin",
    "site_brand": "FindMyTaste",
    "welcome_sign": "Welcome to FindMyTaste Admin Portal",
    "copyright": "FindMyTaste 2025",
    "search_model": ["account.User", "product.Product", "admin_manager.Announcement"],
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],
    "order_with_respect_to": [
        "account",
        "product",
        "admin_manager",
        "vendor",
        "wallet",
        "rider",
    ],
    "icons": {
        "account.User": "fas fa-user",
        "product.Product": "fas fa-utensils",
        "admin_manager.Announcement": "fas fa-bullhorn",
    },
    "custom_links": {
        "admin_manager.Announcement": [
            {
                "name": "Send Push Notification",
                "url": "send_push_notification/",
                "icon": "fas fa-paper-plane",
                "permissions": ["admin_manager.change_announcement"]
            }
        ]
    },
    "show_ui_builder": True,
}

# Optional: Jazzmin color theme (can be customized further)
JAZZMIN_UI_TWEAKS = {
    "theme": "cosmo",
    "dark_mode_theme": "darkly",
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-primary",
    "accent": "accent-primary",
    "navbar": "navbar-primary navbar-dark",
    "no_navbar_border": False,
    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme_color": "#007bff",
}

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

ASGI_APPLICATION = "findmytaste.asgi.application"

AUTH_USER_MODEL = 'account.User'

# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases


CSRF_TRUSTED_ORIGINS = [
    'https://findmytaste-image-latest.onrender.com',
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'findmytastedb',
        'USER': 'postgres',
        'PASSWORD': 'findmytaste-321',
        'HOST':'findmytaste.cduym4i4w6nw.eu-north-1.rds.amazonaws.com' ,
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

TIME_ZONE = 'Africa/Lagos'

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
PAYSTACK_SECRET_KEY=os.getenv('PAYSTACK_SECRET_KEY')
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
    'DEFAULT_RENDERER_CLASSES': (
        'helpers.renderers.UTF8JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ),
}

DEFAULT_CHARSET = 'utf-8'



EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST')
EMAIL_PORT = 587
EMAIL_HOST_USER =  os.getenv('EMAIL_HOST_USER') 
EMAIL_HOST_PASSWORD =  os.getenv('EMAIL_HOST_PASSWORD')
EMAIL_USE_TLS = True

# APPEND_SLASH = False

# CHANNEL_LAYERS = {
#     'default': {
#         'BACKEND': 'channels_redis.core.RedisChannelLayer',
#         'CONFIG': {
#             "hosts": [('127.0.0.1', 6379)],
#         },
#     },
# }
# CHANNEL_LAYERS = {
#     "default": {
#         "BACKEND": "channels_redis.core.RedisChannelLayer",
#         "CONFIG": {
#             "hosts": [('redis', 6379)],
#             # "hosts": [(os.environ.get("REDIS_HOST", "127.0.0.1"), 6379)],
#         },
#     },
# }


# Redis, Cache & Channels Configuration
REDIS_URL = config('REDIS_URL', default='redis://redis:6379/1')

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
        },
    },
}

# Celery Configuration
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE


"""Basic connection example.
"""




try:
    FIREBASE_CREDENTIALS_PATH = os.getenv('FIREBASE_CREDENTIALS_PATH', default='findmytaste-firebase-adminsdk.json')

    if FIREBASE_CREDENTIALS_PATH and os.path.exists(FIREBASE_CREDENTIALS_PATH):
        cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred)
    
    # Confirm initialization
    app = firebase_admin.get_app()
    print(f"Firebase Admin SDK initialized: {app.name}")

except Exception as e:
    print(f"Firebase initialization error: {e}")


# Backblaze B2 Configuration
# Using python-decouple for better environment variable handling
try:
    BACKBLAZE_APPLICATION_KEY_ID = config('BACKBLAZE_APPLICATION_KEY_ID', default=None)
    BACKBLAZE_APPLICATION_KEY = config('BACKBLAZE_APPLICATION_KEY', default=None)
    BACKBLAZE_BUCKET_ID = config('BACKBLAZE_BUCKET_ID', default=None)
    BACKBLAZE_BUCKET_NAME = config('BACKBLAZE_BUCKET_NAME', default=None)
    
    # Check if all required Backblaze credentials are provided
    if not all([BACKBLAZE_APPLICATION_KEY_ID, BACKBLAZE_APPLICATION_KEY, BACKBLAZE_BUCKET_ID, BACKBLAZE_BUCKET_NAME]):
        print("Warning: Backblaze B2 credentials are not fully configured.")
        print("Please create a .env file with the following variables:")
        print("- BACKBLAZE_APPLICATION_KEY_ID")
        print("- BACKBLAZE_APPLICATION_KEY")
        print("- BACKBLAZE_BUCKET_ID")
        print("- BACKBLAZE_BUCKET_NAME")
        print("See .env.example for reference.")
        
except Exception as e:
    print(f"Error loading Backblaze configuration: {e}")
    BACKBLAZE_APPLICATION_KEY_ID = None
    BACKBLAZE_APPLICATION_KEY = None
    BACKBLAZE_BUCKET_ID = None
    BACKBLAZE_BUCKET_NAME = None


# Deep Linking Configuration
from helpers.deep_link_settings import configure_deep_linking_settings

# Configure deep linking settings
globals().update(configure_deep_linking_settings(globals()))