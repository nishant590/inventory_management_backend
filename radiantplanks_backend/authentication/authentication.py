from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework import exceptions
from .models import NewUser
import jwt
import logging

logger = logging.getLogger(__name__)

class JWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return None

        try:
            print(auth_header)
            token = auth_header.split(' ')[1]
            print(token)
            # token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxLCJlbWFpbCI6Im5pc2hhbnRAcHJ1dGhhdGVrLmNvbSIsInVzZXJfdHlwZSI6IkFkbWluIiwiZXhwIjoxNzI5ODUzMjYzLCJwZXJtaXNzaW9ucyI6W119.rhGX-oblmb2thtx9Z4muOHtKUWP_1tnkvVlDgQ5QMt4"
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user = NewUser.objects.get(id=payload['user_id'])
            print(user)
            return (user, token)
        except jwt.ExpiredSignatureError as e:
            logger.error(f"Token expired: {e}")
            raise exceptions.AuthenticationFailed('Token has expired')
        except (jwt.InvalidTokenError, NewUser.DoesNotExist) as e:
            logger.error(f"Authentication failed: {e}")
            raise exceptions.AuthenticationFailed('Invalid token')
