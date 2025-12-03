from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import (
    UserRegistrationSerializer,
    # UserSerializer,
    # UserUpdateSerializer,
    # ChangePasswordSerializer,
    # UserListSerializer,
    # CustomTokenObtainPairSerializer,
    LoginSerializer
)
from .models import User
from .permissions import IsAdminOrReceptionist, IsOwnerOrAdmin


# class UserRegistrationView(generics.CreateAPIView):
#     serializer_class = UserRegistrationSerializer
#     permission_classes = [AllowAny]

class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]

class LogoutView(generics.GenericAPIView):
    """
    API endpoint for user logout
    Blacklists the refresh token
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response(
                    {"error": "Refresh token is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            return Response(
                {"message": "Successfully logged out"},
                status=status.HTTP_205_RESET_CONTENT
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


# class UserViewSet(viewsets.ModelViewSet):
#     # queryset = User.objects.all()
#     serializer_class = UserSerializer
#     permission_classes = [IsAuthenticated]
    
#     def get_queryset(self):
#         '''Filter users based on permissions'''
#         user = self.request.user
#         if user.user_type in ['admin', 'receptionist']:
#             return User.objects.all()
#         # Regular users can only see themselves
#         return User.objects.filter(id=user.id)
    
#     def get_serializer_class(self):
#         """
#         Use fitting serializers based on type of action
#         """
#         if self.action == 'list':
#             return UserListSerializer
#         elif self.action in ['update_profile']:
#             return UserUpdateSerializer
#         elif self.action == 'change_password':
#             return ChangePasswordSerializer
#         return UserSerializer
    
#     @action(detail=False, methods=['get'])
#     def me(self, request):
#         """
#         Get current user's profile
#         """
#         serializer = self.get_serializer(request.user)
#         return Response(serializer.data)
    
#     @action(detail=False, methods=['put', 'patch'])
#     def update_profile(self, request):
#         """
#         Update current user's profile
#         """
#         serializer = self.get_serializer(
#             request.user,
#             data=request.data,
#             partial=True,
#             context={'request': request}
#         )
#         serializer.is_valid(raise_exception=True)
#         serializer.save()
        
#         # Return full user data
#         return Response(UserSerializer(request.user).data)
    
#     @action(detail=False, methods=['post'])
#     def change_password(self, request):
#         """
#         Change current user's password
#         """
#         serializer = self.get_serializer(
#             data=request.data,
#             context={'request': request}
#         )
#         serializer.is_valid(raise_exception=True)
#         serializer.save()
        
#         return Response(
#             {'message': 'Password updated successfully'},
#             status=status.HTTP_200_OK
#         )
