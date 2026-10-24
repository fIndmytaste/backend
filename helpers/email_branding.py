"""
Find my Taste branding shared by every email we send.

The logo travels inside the email (an inline "cid:" image) instead of being
loaded from our server. Outlook, Yahoo and many work inboxes block remote
images until the reader clicks "show images", so a linked logo often showed
as a broken box; an embedded one always displays.
"""

from email.mime.image import MIMEImage
from functools import lru_cache

from django.conf import settings

SENDER = 'Find My Taste <support@findmytaste.com.ng>'

LOGO_CID = 'findmytaste-logo'
# Use as the <img src> in email templates.
LOGO_SRC = f'cid:{LOGO_CID}'
_LOGO_PATH = settings.BASE_DIR / 'static' / 'images' / 'findmytaste-logo-email.png'


@lru_cache(maxsize=1)
def _logo_bytes():
    return _LOGO_PATH.read_bytes()


def attach_logo(message):
    """Embed the logo in an EmailMultiAlternatives whose HTML uses LOGO_SRC."""
    message.mixed_subtype = 'related'
    image = MIMEImage(_logo_bytes(), 'png')
    image.add_header('Content-ID', f'<{LOGO_CID}>')
    image.add_header('Content-Disposition', 'inline', filename='findmytaste-logo.png')
    message.attach(image)
