from rest_framework import serializers
from .models import NewUser, NewGroup, NewPermission

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewUser
        fields = ('id', 'email', 'username', 'phone_number', 'user_type', 
                 'is_active', 'last_login', 'created_at')
        read_only_fields = ('last_login', 'created_at')


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewUser
        fields = ['id', 'email', 'username', 'phone_number', 'is_active', 'user_type']
        read_only_fields = ['id', 'email', 'username']