"""Keep each mobile app to the accounts it is actually for.

Riders were able to sign in to the vendor app and vice versa. Nothing rejected
them, so the vendor app dropped a rider into vendor onboarding and (before the
UserSerializer fix) the server minted an empty Vendor row for them.

Each app identifies itself with an ``X-App-Client`` header. Clients that do not
send one -- the admin dashboard, the customer app, older releases still in the
wild -- are not gated, so this is backwards compatible.
"""

APP_CLIENT_HEADER = 'X-App-Client'

# Which user roles each app accepts. Staff/admin are handled separately.
APP_ALLOWED_ROLES = {
    'vendor': {'vendor'},
    'rider': {'rider'},
    'customer': {'buyer'},
}

# Where we send someone who turned up at the wrong door.
ROLE_HOME_APP = {
    'vendor': 'Vendor',
    'rider': 'Rider',
    'buyer': 'Find My Taste customer',
}

APP_DISPLAY_NAME = {
    'vendor': 'Vendor',
    'rider': 'Rider',
    'customer': 'Find My Taste customer',
}


def get_app_client(request):
    """Return the normalised app identifier, or None when unspecified."""
    raw = request.headers.get(APP_CLIENT_HEADER) or ''
    client = raw.strip().lower()
    return client if client in APP_ALLOWED_ROLES else None


def wrong_app_message(role, app_client):
    """Human-readable explanation for a role/app mismatch."""
    this_app = APP_DISPLAY_NAME.get(app_client, 'this')
    home = ROLE_HOME_APP.get(role)
    if home:
        return (
            f"This is the Find My Taste {this_app} app. This account is "
            f"registered as a {role}, so please sign in with the {home} app "
            f"instead."
        )
    return (
        f"This account is not permitted to sign in to the Find My Taste "
        f"{this_app} app."
    )


def check_app_access(user, request):
    """Return an error message when ``user`` may not use the calling app.

    Returns None when access is fine (including when the caller did not
    identify itself, or when the user is staff/admin).
    """
    app_client = get_app_client(request)
    if app_client is None:
        return None

    # Admins and staff are support accounts and can sign in anywhere.
    if user.role == 'admin' or user.is_staff or user.is_superuser:
        return None

    if user.role in APP_ALLOWED_ROLES[app_client]:
        return None

    return wrong_app_message(user.role, app_client)
