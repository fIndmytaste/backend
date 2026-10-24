"""
Sending email campaigns.

Each recipient gets their own email (never a shared To/BCC list) so addresses
stay private and every message carries a personal unsubscribe link. Sending
runs in Celery; if the broker is unavailable it falls back to a background
thread so the admin's click is never lost.
"""

import logging
import threading

from django.core import signing
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags, urlize
from django.utils.safestring import mark_safe
from decouple import config

from helpers.email_branding import LOGO_SRC, SENDER, attach_logo

logger = logging.getLogger(__name__)

UNSUBSCRIBE_SALT = 'email-campaign-unsubscribe'
FROM_EMAIL = SENDER


def public_base_url():
    return config(
        'PUBLIC_API_BASE_URL',
        default='https://findmytaste-image-latest.onrender.com',
    ).rstrip('/')


def unsubscribe_url_for(user):
    token = signing.dumps(str(user.id), salt=UNSUBSCRIBE_SALT)
    return f"{public_base_url()}/api/v1/email/unsubscribe/{token}/"


def user_id_from_unsubscribe_token(token):
    try:
        return signing.loads(token, salt=UNSUBSCRIBE_SALT)
    except signing.BadSignature:
        return None


LINK_STYLE = 'style="color:#02A57C; text-decoration:underline;"'


def linkify(text):
    """
    Turn web addresses the admin typed in the message into real links.

    The message is plain text, so a pasted address used to arrive as words
    that most inboxes would not open. Text is escaped first; "www." addresses
    get https:// added.
    """
    html = urlize(text, nofollow=False, autoescape=True)
    html = html.replace('<a href="http://www.', '<a href="https://www.')
    return mark_safe(html.replace('<a href=', f'<a target="_blank" {LINK_STYLE} href='))


def button_url(url):
    """Make the button link absolute, so "findmytaste.com.ng/x" still opens."""
    url = (url or '').strip()
    if url and '://' not in url and not url.startswith(('mailto:', 'tel:')):
        url = f'https://{url}'
    return url


def render_campaign(campaign, name=None, unsubscribe_url=None):
    paragraphs = [
        linkify(p.strip()) for p in (campaign.body or '').split('\n\n') if p.strip()]
    context = {
        'campaign': campaign,
        'greeting_name': (name or '').split(' ')[0] if name else '',
        'paragraphs': paragraphs,
        'cta_url': button_url(campaign.cta_url),
        'unsubscribe_url': unsubscribe_url,
        'logo_src': LOGO_SRC,
        'current_year': timezone.now().year,
    }
    html = render_to_string('emails/campaign.html', context)
    return html, strip_tags(html)


def send_campaign_email(campaign, email, name=None, unsubscribe_url=None):
    from django.core.mail import EmailMultiAlternatives

    html, text = render_campaign(campaign, name=name, unsubscribe_url=unsubscribe_url)
    headers = {}
    if unsubscribe_url:
        # Lets Gmail/Outlook show their own one-click "Unsubscribe" button.
        headers['List-Unsubscribe'] = f'<{unsubscribe_url}>'
    message = EmailMultiAlternatives(
        subject=campaign.subject,
        body=text,
        from_email=FROM_EMAIL,
        to=[email],
        headers=headers,
    )
    message.attach_alternative(html, 'text/html')
    attach_logo(message)
    try:
        message.send(fail_silently=False)
        return True
    except Exception as error:
        logger.warning('Campaign %s to %s failed: %s', campaign.id, email, error)
        return False


def send_campaign(campaign_id):
    """Send a campaign that is already marked 'sending'. Safe to call once."""
    from admin_manager.models import EmailCampaign

    campaign = EmailCampaign.objects.filter(id=campaign_id, status='sending').first()
    if campaign is None:
        return

    sent = failed = 0
    last_error = ''
    for user in campaign.recipients().only('id', 'email', 'full_name').iterator():
        ok = send_campaign_email(
            campaign, user.email, name=user.full_name,
            unsubscribe_url=unsubscribe_url_for(user),
        )
        if ok:
            sent += 1
        else:
            failed += 1
            last_error = f'Could not deliver to some recipients (last: {user.email}).'
        # Progress for the dashboard every 25 emails.
        if (sent + failed) % 25 == 0:
            EmailCampaign.objects.filter(id=campaign.id).update(
                sent_count=sent, failed_count=failed)

    EmailCampaign.objects.filter(id=campaign.id).update(
        sent_count=sent,
        failed_count=failed,
        last_error=last_error,
        status='sent' if sent else 'failed',
        sent_at=timezone.now(),
    )
    logger.info('Campaign %s finished: %s sent, %s failed', campaign.id, sent, failed)


def queue_campaign(campaign_id):
    try:
        from admin_manager.tasks import send_email_campaign_task
        send_email_campaign_task.delay(str(campaign_id))
    except Exception as error:
        logger.warning('Celery unavailable for campaign %s (%s); sending in a thread.', campaign_id, error)
        thread = threading.Thread(target=send_campaign, args=(campaign_id,), daemon=True)
        thread.start()
