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
import os
from datetime import datetime
from authentication.db_backup import manage_backups
from django.http import FileResponse
import jwt
from django.core.mail import send_mail
from datetime import datetime, timedelta
from jwt import ExpiredSignatureError, DecodeError
from django.core.paginator import Paginator


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
    permission_classes = [IsAuthenticated]
    def post(self, request):
        try:
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
        except Exception as e:
            log.app.error(f"Error in user creation {str(e)}")
            log.trace.trace(f"Error in user creation {traceback.format_exc()}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
            ip_address = request.META.get('HTTP_X_FORWARDED_FOR')
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
                              ip_add=request.META.get('HTTP_X_FORWARDED_FOR'), 
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


class ForgotPasswordAPIView(APIView):
    permission_classes = [AllowAny]
    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        if not email:
            return Response({"error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = NewUser.objects.get(email=email)
            # Generate token
            secret_key = settings.SECRET_KEY
            payload = {
                "user_id": user.id,
                "exp": datetime.utcnow() + timedelta(hours=1),  # Token valid for 1 hour
            }
            reset_token = jwt.encode(payload, secret_key, algorithm="HS256")
            
            # Send reset email
            reset_url = f"https://bill.radiantplanks.com/reset/?token={reset_token}"
            send_mail(
                subject="Password Reset Request",
                message=f"Click the link to reset your password: {reset_url}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
            )
            return Response({"message": "Password reset link has been sent to your email."}, status=status.HTTP_200_OK)
        except NewUser.DoesNotExist:
            return Response({"error": "User with this email does not exist."}, status=status.HTTP_404_NOT_FOUND)


class ResetPasswordAPIView(APIView):
    permission_classes = [AllowAny]
    def post(self, request, *args, **kwargs):
        token = request.data.get('token')
        new_password = request.data.get('new_password')
        
        if not token or not new_password:
            return Response({"error": "Token and new password are required."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Decode token
            secret_key = settings.SECRET_KEY
            payload = jwt.decode(token, secret_key, algorithms=["HS256"])
            
            # Fetch user
            user_id = payload.get("user_id")
            user = NewUser.objects.get(id=user_id)
            
            # Update password
            user.set_password(new_password)
            user.save()
            log.audit.success(f"User changed password in : {user.username} | | ")
            return Response({"message": "Password has been reset successfully."}, status=status.HTTP_200_OK)
            
        except ExpiredSignatureError:
            return Response({"error": "The token has expired."}, status=status.HTTP_400_BAD_REQUEST)
        except DecodeError:
            return Response({"error": "Invalid token."}, status=status.HTTP_400_BAD_REQUEST)
        except NewUser.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)


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

    def get(self, request, id):
        try:
            user = NewUser.objects.get(id=id)
        except NewUser.DoesNotExist:
            raise exceptions.NotFound('User not found')

        serializer = UserSerializer(user)
        return Response(serializer.data)

    def put(self, request, id):
        try:
            user = NewUser.objects.get(id=id)
        except NewUser.DoesNotExist:
            raise exceptions.NotFound('User not found')

        serializer = UserSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)


class CreateBackup(APIView):
    """API endpoint to trigger database backup."""

    def get(self, request):
        """API endpoint to handle database backups and provide a downloadable file."""
        is_human_readable = request.GET.get("is_human_readable", "false").lower() == "true"
        is_compressed = request.GET.get("is_compressed", "true").lower() == "true"
        
        # Trigger the backup process
        result = manage_backups(
            database_type="sqlite",  # You can modify this for other databases
            compress=is_compressed,
            human_readable=is_human_readable,
        )

        if result["status"] == "success":
            backup_file_path = result["file"]

            if os.path.exists(backup_file_path):
                # Serve the file for download
                response = FileResponse(
                    open(backup_file_path, "rb"),
                    as_attachment=True,
                    filename=os.path.basename(backup_file_path)
                )
                return response
            else:
                return Response(
                    {"message": "Backup file not found after creation."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        else:
            return Response(
                {"message": "Backup process failed", "error": result["message"]},
                status=status.HTTP_400_BAD_REQUEST
            )
        

class AuditLogListView(APIView):
    """
    API endpoint to fetch audit logs without using a serializer.
    """
    def get(self, request):
        query_params = request.GET

        # Filtering based on query parameters
        user_id = query_params.get('user_id')
        action = query_params.get('action')
        model_name = query_params.get('model_name')

        logs = AuditLog.objects.all()

        if user_id:
            logs = logs.filter(user_id=user_id)
        if action:
            logs = logs.filter(action=action)
        if model_name:
            logs = logs.filter(model_name=model_name)

        # Paginate the results
        page = query_params.get('page', 1)
        page_size = int(query_params.get('page_size', 10))
        paginator = Paginator(logs, page_size)

        try:
            paginated_logs = paginator.page(page)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Prepare response data without using serializer
        log_data = [
            {
                "id": log.id,
                "user": log.user.username,
                "action": log.action,
                "model_name": log.model_name,
                "record_id": log.record_id,
                "timestamp": log.timestamp.isoformat(),
                "details": log.details,
                "activity_ip": log.activity_ip,
                "activity_city": log.activity_city,
                "activity_country": log.activity_country,
            }
            for log in paginated_logs
        ]

        return Response(
            {
                "count": paginator.count,
                "num_pages": paginator.num_pages,
                "current_page": paginated_logs.number,
                "results": log_data,
            },
            status=status.HTTP_200_OK,
        )
