from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Account
from django.core.exceptions import ValidationError


class AddAccountAPI(APIView):
    def post(self, request):
        try:
            # Retrieve data from request
            name = request.data.get('name')
            account_type = request.data.get('account_type')
            code = request.data.get('code')
            description = request.data.get('description', '')
            is_active = request.data.get('is_active', True)

            # Validate the required fields
            if not name or not account_type or not code:
                return Response(
                    {"message": "Missing required fields: name, account_type, and code."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate account type
            valid_account_types = ['asset', 'liability', 'equity', 'income', 'expense']
            if account_type not in valid_account_types:
                return Response(
                    {"message": f"Invalid account type. Valid types are {valid_account_types}."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Ensure the account code is unique
            if Account.objects.filter(code=code).exists():
                return Response(
                    {"message": "Account with this code already exists."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create the Account
            account = Account.objects.create(
                name=name,
                account_type=account_type,
                code=code,
                description=description,
                is_active=is_active
            )

            # Return success response
            return Response(
                {"message": "Account created successfully!", "data": {
                    "name": account.name,
                    "account_type": account.account_type,
                    "code": account.code,
                    "description": account.description,
                    "is_active": account.is_active
                }},
                status=status.HTTP_201_CREATED
            )

        except ValidationError as e:
            return Response(
                {"message": f"Validation error: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"message": f"Error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AccountListView(APIView):
    def get(self, request, *args, **kwargs):
        accounts = Account.objects.filter(is_active=True).order_by('name')
        account_data = [
            {
                'id': account.id,
                'name': account.name,
                'account_type': account.account_type,
                'code': account.code,
                'description': account.description,
                'balance': float(account.balance),  # Convert Decimal to float
                'created_at': account.created_at.isoformat(),
                'updated_at': account.updated_at.isoformat(),
                'is_active': account.is_active,
            }
            for account in accounts
        ]
        return Response({'accounts': account_data}, status=status.HTTP_200_OK)