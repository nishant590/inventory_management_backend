from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from .models import NewUser, NewGroup, NewPermission, AuditLog
from .serializers import UserSerializer, LoginSerializer
from rest_framework import exceptions
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser,AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
import requests
from radiantplanks_backend.logging import log
import traceback

def get_geolocation_based_on_ip(ip):
    url = f"https://ipinfo.io/{ip}/json"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
    except requests.RequestException:
        pass
    return {}

def audit_log(user, action,  ip_add, model_name=None, record_id=None, additional_details=None):
    """
    Simple utility function for creating audit logs
    """
    try:
        # Get geolocation based on IP
        geolocation = get_geolocation_based_on_ip(ip_add)
        AuditLog.objects.create(
            user=user,
            action=action,
            model_name=model_name,
            record_id=record_id,
            details=additional_details,
            activity_ip=ip_add,
            activity_city=geolocation.get("city",""),
            activity_country=geolocation.get("country","")
        )
        return True
    except Exception as e:
        # Basic error logging - could be replaced with proper logging
        log.app.error(f"Error creating audit log: {str(e)}")
        log.trace.trace(f"Error creating audit log: {traceback.format_exc()}")
        return False


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
            log.app.error('Email already exists')
            return Response({"error": "Email already in use"}, status=status.HTTP_400_BAD_REQUEST)
        if NewUser.objects.filter(username=username).exists():
            log.app.error('Username already exists')
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
        log.audit.success(f"User added successfully | {username} | ")
        audit_log_entry = audit_log(user=request.user,
                              action="Create User", 
                              ip_add=request.META.get('REMOTE_ADDR'), 
                              model_name="NewUser", 
                              record_id=user.id)
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
                log.app.error('Invalid password')
                user.failed_login_attempts += 1
                user.save()
                raise exceptions.AuthenticationFailed('Invalid credentials')

            if not user.is_active:
                raise exceptions.AuthenticationFailed('User is inactive')

            # Capture IP and get geolocation
            ip_address = request.META.get('REMOTE_ADDR')
            geo_data = self.get_geolocation(ip_address)
            last_login_time = user.last_login
            last_login_ip = user.last_login_ip

            # Update login stats
            user.last_login = timezone.now()
            user.last_login_ip = ip_address
            user.last_login_city = geo_data.get('city')
            user.last_login_country = geo_data.get('country')
            user.failed_login_attempts = 0
            user.save()

            token = RefreshToken.for_user(user)
            log.audit.success(f"User logged in : {user.username} | logintime : {user.last_login}")
            audit_log_entry = audit_log(user=user,
                              action="Login", 
                              ip_add=request.META.get('REMOTE_ADDR'), 
                              model_name="NewUser", 
                              record_id=user.id)
            return Response({
                'refresh': str(token),
                'access': str(token.access_token),
                'user': UserSerializer(user).data,
                'last_login_time': last_login_time,
                'last_login_ip': last_login_ip
            })

        except NewUser.DoesNotExist:
            log.trace.trace("Exception : User does not exsists")
            raise exceptions.AuthenticationFailed('Invalid credentials')

    def get_geolocation(self, ip):
        url = f"https://ipinfo.io/{ip}/json"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return response.json()
        except requests.RequestException:
            pass
        return {}


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