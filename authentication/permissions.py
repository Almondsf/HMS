from rest_framework import permissions


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

