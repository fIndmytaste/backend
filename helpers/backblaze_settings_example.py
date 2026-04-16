# helpers/backblaze_settings_example.py
"""
Example settings configuration for Backblaze B2 integration

Add these settings to your Django settings.py file:
"""

# Backblaze B2 Configuration
# Get these values from your Backblaze B2 account:
# 1. Go to https://secure.backblaze.com/b2_buckets.htm
# 2. Create an application key with appropriate permissions
# 3. Note down your bucket ID and name

BACKBLAZE_APPLICATION_KEY_ID = 'your_application_key_id_here'
BACKBLAZE_APPLICATION_KEY = 'your_application_key_here'
BACKBLAZE_BUCKET_ID = 'your_bucket_id_here'
BACKBLAZE_BUCKET_NAME = 'your_bucket_name_here'

# Optional: You can also use environment variables
# BACKBLAZE_APPLICATION_KEY_ID = os.getenv('BACKBLAZE_APPLICATION_KEY_ID')
# BACKBLAZE_APPLICATION_KEY = os.getenv('BACKBLAZE_APPLICATION_KEY')
# BACKBLAZE_BUCKET_ID = os.getenv('BACKBLAZE_BUCKET_ID')
# BACKBLAZE_BUCKET_NAME = os.getenv('BACKBLAZE_BUCKET_NAME')

"""
Environment variables (.env file):
BACKBLAZE_APPLICATION_KEY_ID=your_application_key_id_here
BACKBLAZE_APPLICATION_KEY=your_application_key_here
BACKBLAZE_BUCKET_ID=your_bucket_id_here
BACKBLAZE_BUCKET_NAME=your_bucket_name_here
"""