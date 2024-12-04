from django.db import models
from django.contrib.auth.hashers import make_password, check_password
import jwt
from datetime import datetime, timedelta

class NewPermission(models.Model):
    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class NewGroup(models.Model):
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(null=True, blank=True)
    permissions = models.ManyToManyField(NewPermission, related_name='groups')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class NewUser(models.Model):
    email = models.EmailField(unique=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    last_login_city = models.CharField(max_length=100, null=True, blank=True)
    last_login_country = models.CharField(max_length=100, null=True, blank=True)
    username = models.CharField(max_length=150, unique=True)
    password = models.CharField(max_length=128)  # Will store hashed password
    phone_number = models.CharField(max_length=15, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    USER_TYPES = [
        ('admin', 'Administrator'),
        ('manager', 'Manager'),
        ('staff', 'Staff'),
        ('warehouse', 'Warehouse Staff'),
    ]
    user_type = models.CharField(max_length=20, choices=USER_TYPES, default='staff')
    
    # Groups and permissions
    groups = models.ManyToManyField(NewGroup, related_name='users')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Login tracking
    last_login = models.DateTimeField(null=True, blank=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    login_count = models.IntegerField(default=0)
    failed_login_attempts = models.IntegerField(default=0)
    last_failed_login = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.email

    def set_password(self, raw_password):
        self.password = make_password(raw_password)
        
    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    @property
    def is_authenticated(self):
        """Override this method to work with Django authentication system."""
        return True
    
    @property
    def permissions(self):
        """Get all permissions from all groups"""
        return NewPermission.objects.filter(groups__users=self).distinct()

    def has_permission(self, permission_code):
        return self.permissions.filter(code=permission_code).exists()

    def generate_jwt(self, secret_key, expires_delta=timedelta(hours=1)):
        expire = datetime.now() + expires_delta
        payload = {
            "user_id": self.id,
            "email": self.email,
            "user_type": self.user_type,
            "exp": expire,
            "permissions": [p.code for p in self.permissions.all()]
        }
        return jwt.encode(payload, secret_key, algorithm="HS256")


class AuditLog(models.Model):
    """
    Simple and lightweight audit logging model
    """
    user = models.ForeignKey(NewUser, on_delete=models.CASCADE)
    action = models.CharField(max_length=100)  # e.g., 'create_product', 'update_invoice'
    model_name = models.CharField(max_length=100)  # e.g., 'Product', 'Invoice'
    record_id = models.IntegerField()  # ID of the affected record
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.CharField(max_length=200, null=True, blank=True)  # Flexible additional info
    activity_ip = models.CharField(max_length=100, null=True, blank=True)
    activity_city = models.CharField(max_length=100, null=True, blank=True)
    activity_country = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'action', 'timestamp']),
            models.Index(fields=['model_name', 'record_id'])
        ]
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.username} - {self.action} on {self.model_name}"