from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from .models import NewUser, NewGroup, NewPermission
from .serializers import UserSerializer, LoginSerializer
from rest_framework import exceptions
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser,AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken


class RegisterAPIView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        data = request.data
        email = data.get('email')
        username = data.get('username')
        password = data.get('password')
        phone_number = data.get('phone_number')
        user_type = data.get('user_type', 'staff')
        
        # Check if email or username already exists
        if NewUser.objects.filter(email=email).exists():
            return Response({"error": "Email already in use"}, status=status.HTTP_400_BAD_REQUEST)
        if NewUser.objects.filter(username=username).exists():
            return Response({"error": "Username already in use"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Create the user
        user = NewUser.objects.create(
            email=email,
            username=username,
            phone_number=phone_number,
            user_type=user_type,
        )
        user.set_password(password)
        user.save()
        
        return Response({"message": "User registered successfully"}, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        password = serializer.validated_data['password']

        try:
            user = NewUser.objects.get(email=email)
            if not user.check_password(password):
                user.failed_login_attempts += 1
                user.last_failed_login = timezone.now()
                user.save()
                raise exceptions.AuthenticationFailed('Invalid credentials')

            if not user.is_active:
                raise exceptions.AuthenticationFailed('User is inactive')

            # Update login stats
            user.last_login = timezone.now()
            user.login_count += 1
            user.failed_login_attempts = 0
            user.last_login_ip = request.META.get('REMOTE_ADDR')
            user.save()

            # Generate refresh and access tokens
            refresh = RefreshToken.for_user(user)
            access = refresh.access_token

            return Response({
                'refresh': str(refresh),
                'access': str(access),
                'user': UserSerializer(user).data
            })

        except NewUser.DoesNotExist:
            raise exceptions.AuthenticationFailed('Invalid credentials')


class UserListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        users = NewUser.objects.all()
        
        # Manually serialize the data
        users_data = [
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "created_at": user.created_at,
                # Add any other fields you need to include
            }
            for user in users
        ]

        return Response(users_data, status=status.HTTP_200_OK)


class UserDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            user = NewUser.objects.get(pk=pk)
        except NewUser.DoesNotExist:
            raise exceptions.NotFound('User not found')

        serializer = UserSerializer(user)
        return Response(serializer.data)

    def put(self, request, pk):
        try:
            user = NewUser.objects.get(pk=pk)
        except NewUser.DoesNotExist:
            raise exceptions.NotFound('User not found')

        serializer = UserSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)