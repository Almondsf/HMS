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


class IsAdminOrReceptionist(permissions.BasePermission):
    '''
    Permission for admin and receptionist roles
    They can manage all users
    '''
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            request.user.user_type in ['admin', 'receptionist']
        )

    def has_object_permission(self, request, view, obj):
        # Admin/Receptionist can access any user object
        return (
            request.user and
            request.user.is_authenticated and
            request.user.user_type in ['admin', 'receptionist']
        )


class IsOwnerOrAdmin(permissions.BasePermission):
    '''
    Users can only access/modify their own data
    Admins can access/modify anyone's data
    '''
    def has_object_permission(self, request, view, obj):
        # Admin/Receptionist can access anyone
        if request.user.user_type in ['admin', 'receptionist']:
            return True

        # Users can only access themselves
        return obj == request.user

