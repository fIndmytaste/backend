from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from account.models import StaffPagePermission
from helpers.response.response_format import success_response, bad_request_response


class StaffPagePermissionsView(generics.GenericAPIView):
    """
    GET /admin-manager/staff/my-pages/

    Returns the list of custom-admin pages the authenticated staff user
    has been granted access to.

    Superusers receive access to all pages automatically.
    Non-staff users receive an empty list (they should not reach the admin).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Superusers see everything
        if user.is_superuser:
            pages = [p[0] for p in StaffPagePermission.PAGE_CHOICES]
            return success_response(data={
                'is_superuser': True,
                'pages': pages,
                'marketplaces': [],
            })

        # Non-staff users have no access
        if not user.is_staff:
            return success_response(data={
                'is_superuser': False,
                'pages': [],
                'marketplaces': [],
            })

        # Staff user — return only explicitly granted pages
        granted = (
            StaffPagePermission.objects.filter(user=user)
            .values_list('page', flat=True)
        )
        marketplaces = [
            {
                'id': str(assignment.marketplace_id),
                'name': assignment.marketplace.name,
            }
            for assignment in user.marketplace_assignments.select_related('marketplace')
        ]
        return success_response(data={
            'is_superuser': False,
            'pages': list(granted),
            'marketplaces': marketplaces,
        })
