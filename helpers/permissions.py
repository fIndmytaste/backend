from rest_framework.permissions import BasePermission

class IsVendor(BasePermission):
    """
    Custom permission to only allow vendors to access certain views.
    """
    def has_permission(self, request, view):
        # Check if the user is authenticated
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if the user is a vendor (assuming the Vendor model has a OneToOne relationship with User)
        try:
            # Check if the authenticated user has an associated Vendor profile
            request.user.vendor
            return True  # User is a vendor
        except AttributeError:
            return False  # User is not a vendor
