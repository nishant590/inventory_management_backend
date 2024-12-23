from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (LoginView, 
                    RegisterAPIView, 
                    UserListView, 
                    UserDetailView, 
                    CreateBackup,
                    ResetPasswordAPIView,
                    AuditLogListView,
                    ForgotPasswordAPIView) 
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

router = DefaultRouter()



urlpatterns = [
    path('register/', RegisterAPIView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('forgot-password/', ForgotPasswordAPIView.as_view(), name='forgot password'),
    path('reset-password/', ResetPasswordAPIView.as_view(), name='reset password'),
    path('list_user/', UserListView.as_view(), name='list_user'),
    path('update_user/<int:id>/', UserDetailView.as_view(), name='update_user'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('createbackup/', CreateBackup.as_view(), name='db_backup'),
    path('audit-logs/', AuditLogListView.as_view(), name='audit-logs'),
]