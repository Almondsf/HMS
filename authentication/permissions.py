from rest_framework import permissions

from .models import User

Role = User.UserType

STAFF_ROLES = tuple(role for role in Role.values if role != Role.PATIENT)


def allow_roles(read=(), write=()):
    '''
    Build a permission class from role lists.
    `read` roles may use safe methods (GET/HEAD/OPTIONS) only;
    `write` roles may use every method. Superusers are always allowed.

    Usage: permission_classes = [allow_roles(read=[Role.DOCTOR], write=[Role.ADMIN])]
    '''
    read, write = frozenset(read), frozenset(write)

    class RolePermission(permissions.BasePermission):
        def has_permission(self, request, view):
            user = request.user
            if not (user and user.is_authenticated):
                return False
            if user.is_superuser:
                return True
            if request.method in permissions.SAFE_METHODS:
                return user.user_type in read or user.user_type in write
            return user.user_type in write

    return RolePermission
