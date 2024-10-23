from rest_framework import permissions

class HasPermission(permissions.BasePermission):
    def __init__(self, required_permission):
        self.required_permission = required_permission

    def has_permission(self, request, view):
        return request.user.has_permission(self.required_permission)