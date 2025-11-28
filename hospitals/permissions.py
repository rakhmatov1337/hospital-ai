from rest_framework.permissions import BasePermission

from accounts.models import User


class IsHospitalUser(BasePermission):
    """
    Allows access only to authenticated users with the hospital role.
    """

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, 'role', None) == User.Roles.HOSPITAL
        )

