from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import LoginView, RegisterAPIView, UserListView, UserDetailView 
from rest_framework.routers import DefaultRouter

router = DefaultRouter()



urlpatterns = [
    path('register/', RegisterAPIView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('list_user/', UserListView.as_view(), name='list_user'),
    path('update_user/', UserDetailView.as_view(), name='update_user'),

]