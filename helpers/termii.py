"""
Termii SMS client, used to send phone-verification codes.

We generate and check the code ourselves (VerificationCode, type 'phone') and
only use Termii to deliver it. That keeps verification in our own database, so
test accounts, expiry and "which number was this code for" behave the same as
the email codes, and switching SMS provider never touches the auth flow.

Configuration (environment):
    TERMII_API_KEY     Live key from app.termii.ai -> Settings -> API Keys.
    TERMII_BASE_URL    Defaults to https://v4.api.termii.com (the dashboard's
                       base URL for this workspace).
    TERMII_SENDER_ID   An approved sender ID. Required for the 'dnd' channel.
    TERMII_CHANNEL     'dnd' (default, reaches DND numbers; needs an approved
                       sender ID) or 'generic'.
"""

import logging
import re

import requests
from decouple import config

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = 'https://v4.api.termii.com'


class TermiiError(Exception):
    """Raised when an SMS could not be handed to Termii."""


def normalize_nigerian_phone(raw):
    """
    Return the number in international format without '+' (2348012345678),
    which is what Termii expects, or None if it is not a plausible number.

    Accepts 08012345678, 8012345678, +2348012345678, 2348012345678 and the
    same with spaces or dashes.
    """
    digits = re.sub(r'\D', '', str(raw or ''))
    if not digits:
        return None
    if digits.startswith('234') and len(digits) == 13:
        return digits
    if digits.startswith('0') and len(digits) == 11:
        return '234' + digits[1:]
    if len(digits) == 10 and digits[0] in '789':
        return '234' + digits
    # Other countries: accept a plausible full international number as-is.
    if 11 <= len(digits) <= 15 and not digits.startswith('0'):
        return digits
    return None


def is_configured():
    return bool(config('TERMII_API_KEY', default=''))


def send_sms(to, message):
    """
    Send one SMS through Termii. Returns Termii's message_id.
    Raises TermiiError with a user-presentable reason on failure.
    """
    api_key = config('TERMII_API_KEY', default='')
    if not api_key:
        raise TermiiError('SMS is not configured yet. Please try again later.')

    base_url = config('TERMII_BASE_URL', default=DEFAULT_BASE_URL).rstrip('/')
    payload = {
        'api_key': api_key,
        'to': to,
        'from': config('TERMII_SENDER_ID', default='N-Alert'),
        'sms': message,
        'type': 'plain',
        'channel': config('TERMII_CHANNEL', default='dnd'),
    }

    try:
        response = requests.post(f'{base_url}/api/sms/send', json=payload, timeout=15)
    except requests.RequestException as error:
        logger.error('Termii request failed: %s', error)
        raise TermiiError('Could not send the SMS right now. Please try again.') from error

    try:
        body = response.json()
    except ValueError:
        body = {}

    if response.ok and (body.get('message_id') or body.get('message_id_str')):
        return body.get('message_id_str') or body.get('message_id')

    # Never log the API key; the payload is rebuilt without it.
    logger.error(
        'Termii rejected SMS to %s (%s): %s',
        to, response.status_code, body or response.text[:300],
    )
    raise TermiiError('Could not send the SMS right now. Please try again.')


def send_voice_code(to, code):
    """
    Phone [to] and read out [code] (Termii Voice Call API).

    The fallback when an SMS never arrives: some networks reject our sender
    ID (Termii swaps in another one and the network drops it), but a call
    always gets through. Codes must be 4-8 digits and must not start with 0
    (Termii takes the code as a number). Raises TermiiError on failure.
    """
    api_key = config('TERMII_API_KEY', default='')
    if not api_key:
        raise TermiiError('Calls are not configured yet. Please try again later.')
    code = str(code)
    if not (code.isdigit() and 4 <= len(code) <= 8 and not code.startswith('0')):
        raise TermiiError('This code cannot be read out by phone. Request a new code.')

    base_url = config('TERMII_BASE_URL', default=DEFAULT_BASE_URL).rstrip('/')
    payload = {'api_key': api_key, 'phone_number': to, 'code': int(code)}
    try:
        response = requests.post(
            f'{base_url}/api/sms/otp/send/voice', json=payload, timeout=15)
    except requests.RequestException as error:
        logger.error('Termii voice request failed: %s', error)
        raise TermiiError('Could not call you right now. Please try again.') from error

    try:
        body = response.json()
    except ValueError:
        body = {}

    if response.ok and (body.get('code') == 'ok' or body.get('message_id') or body.get('pinId')):
        return body.get('message_id') or body.get('pinId')

    logger.error(
        'Termii rejected voice code to %s (%s): %s',
        to, response.status_code, body or response.text[:300],
    )
    raise TermiiError('Could not call you right now. Please try again.')

