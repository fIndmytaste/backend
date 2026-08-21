from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken


class TokenManager:

    @staticmethod
    def get_tokens_for_user(user):
        """Issue a token pair and record that the user just signed in.

        Django only maintains `last_login` through `auth.login()`, which a JWT
        flow never calls -- so the field stayed null forever and the admin
        dashboard's Customer Management tab reported "Never" for everyone,
        including people who had just signed in.

        Every sign-in path funnels through here (the token-refresh endpoint
        does not), so this is the one place that reliably means "a session just
        started". update_fields keeps it to a single-column write.
        """
        refresh = RefreshToken.for_user(user)

        try:
            user.last_login = timezone.now()
            user.save(update_fields=['last_login'])
        except Exception:
            # Never block a sign-in over a bookkeeping field.
            import logging
            logging.getLogger(__name__).exception(
                "Could not update last_login for user %s", getattr(user, 'id', None),
            )

        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }
