"""
App update checks.

    GET /api/v1/app-version/check/?app=rider&platform=android&version=1.0.3

Response data:
    {
      "update_available": true,      # a newer release exists
      "force_update": false,         # this version is below the minimum
      "latest_version": "1.0.4",
      "minimum_version": "1.0.2",
      "store_url": "https://play.google.com/...",
      "release_notes": "..."
    }

With no policy configured for the app/platform, nothing is ever forced, so
shipping the client before configuring the admin page is safe.
"""

import re

from rest_framework import generics
from rest_framework.permissions import AllowAny

from helpers.response.response_format import bad_request_response, success_response

_VERSION_RE = re.compile(r'^\s*v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:\.(\d+))?(?:[+-].*)?\s*$')


def parse_version(value):
    """'1.0.3+5' -> (1, 0, 3, 0); None when it is not a version."""
    match = _VERSION_RE.match(str(value or ''))
    if not match:
        return None
    return tuple(int(part or 0) for part in match.groups())


class AppVersionCheckView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        from admin_manager.models import AppVersionPolicy

        app = (request.GET.get('app') or '').strip().lower()
        platform = (request.GET.get('platform') or '').strip().lower()
        current = parse_version(request.GET.get('version'))

        if app not in dict(AppVersionPolicy.APP_CHOICES):
            return bad_request_response(message='Unknown app.')
        if platform not in dict(AppVersionPolicy.PLATFORM_CHOICES):
            return bad_request_response(message='Unknown platform.')

        policy = AppVersionPolicy.objects.filter(
            app=app, platform=platform, is_active=True).first()
        if policy is None or current is None:
            return success_response(data={
                'update_available': False,
                'force_update': False,
                'latest_version': policy.latest_version if policy else None,
                'minimum_version': (policy.minimum_version or None) if policy else None,
                'store_url': policy.store_url if policy else None,
                'release_notes': policy.release_notes if policy else '',
            })

        latest = parse_version(policy.latest_version)
        minimum = parse_version(policy.minimum_version) if policy.minimum_version else None

        return success_response(data={
            'update_available': bool(latest and current < latest),
            'force_update': bool(minimum and current < minimum),
            'latest_version': policy.latest_version,
            'minimum_version': policy.minimum_version or None,
            'store_url': policy.store_url or None,
            'release_notes': policy.release_notes or '',
        })
