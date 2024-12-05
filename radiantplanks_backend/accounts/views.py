from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Account, ReceivableTracking, Transaction, TransactionLine, PayableTracking
from django.core.exceptions import ValidationError
from django.db.models import Sum, Q
from django.http import JsonResponse
from rest_framework.permissions import IsAuthenticated
from decimal import Decimal
import pandas as pd
from radiantplanks_backend.logging import log
import traceback
from authentication.views import audit_log


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
                log.app.error("Invalid name or account type or code provided")
                return Response(
                    {"message": "Missing required fields: name, account_type, and code."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate account type
            valid_account_types = ['asset', 'liability', 'equity', 'income', 'expense']
            if account_type not in valid_account_types:
                log.app.error("Invalid account type provided")
                return Response(
                    {"message": f"Invalid account type. Valid types are {valid_account_types}."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Ensure the account code is unique
            if Account.objects.filter(code=code).exists():
                log.app.error("Account code already exists")
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
            log.audit.success(f"Account created successfully | {account.name} | {request.user}")
            audit_log_entry = audit_log(user=request.user,
                              action="Account Created", 
                              ip_add=request.META.get('REMOTE_ADDR'), 
                              model_name="NewUser", 
                              record_id=account.id)
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
            log.trace.trace(f"Validation error: {str(e)}, {traceback.format_exc()}")
            return Response(
                {"message": f"Validation error: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            log.trace.trace(f"Error while creating account {traceback.format_exc()}")
            return Response(
                {"message": f"Error: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
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
    

class AccountReceivablesView(APIView):
    def get(self, request):
        try:
            # Fetch data from the database directly as a queryset
            receivables = ReceivableTracking.objects.values(
                "customer__business_name", "payable_amount"
            )
            
            # Convert the queryset to a pandas DataFrame
            df = pd.DataFrame.from_records(receivables, columns=["customer__business_name", "receivable_amount"])
            
            if df.empty:
                # Handle empty table scenario
                return Response(
                    {
                        "data": [],
                        "overall_receivable": 0,
                    },
                    status=status.HTTP_200_OK,
                )
            
            # Rename columns for a clean response
            df.rename(columns={"customer__business_name": "customer"}, inplace=True)
            
            # Calculate overall receivable amount
            overall_receivable = df["receivable_amount"].sum()
            
            # Convert DataFrame back to a dictionary
            receivables_data = df.to_dict(orient="records")
            audit_log_entry = audit_log(user=request.user,
                              action="Receivable Reports viewed", 
                              ip_add=request.META.get('REMOTE_ADDR'), 
                              model_name="ReceivableTracking", 
                              record_id=0)
            
            return Response(
                {
                    "data": receivables_data,
                    "overall_receivable": overall_receivable,
                },
                status=status.HTTP_200_OK,
            )
        
        except Exception as e:
            log.trace.trace(f"Error while fetching receivables data, {traceback.format_exc()}")
            # Handle unexpected errors
            return Response(
                {
                    "detail": "An error occurred while processing the request.",
                    "error": str(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
    

class AccountPayablesView(APIView):
    def get(self, request):
        try:
            # Fetch data from the database directly as a queryset
            payables = PayableTracking.objects.values(
                "vendor__business_name", "payable_amount"
            )
            
            # Convert the queryset to a pandas DataFrame
            df = pd.DataFrame.from_records(payables, columns=["vendor__business_name", "payable_amount"])
            
            if df.empty:
                # Handle empty table scenario
                return Response(
                    {
                        "data": [],
                        "overall_payables": 0,
                    },
                    status=status.HTTP_200_OK,
                )
            
            # Rename columns for a clean response
            df.rename(columns={"vendor__business_name": "vendor"}, inplace=True)
            
            # Calculate overall receivable amount
            overall_receivable = df["payable_amount"].sum()
            
            # Convert DataFrame back to a dictionary
            payables_data = df.to_dict(orient="records")
            audit_log_entry = audit_log(user=request.user,
                              action="Payable Reports viewed", 
                              ip_add=request.META.get('REMOTE_ADDR'), 
                              model_name="PayableTracking", 
                              record_id=0)
            return Response(
                {
                    "data": payables_data,
                    "overall_payable": overall_receivable,
                },
                status=status.HTTP_200_OK,
            )
        
        except Exception as e:
            log.trace.trace(f"Error while fetching payables data, {traceback.format_exc()}")
            # Handle unexpected errors
            return Response(
                {
                    "detail": "An error occurred while processing the request.",
                    "error": str(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


class BalanceSheetView(APIView):
    """
    API view to generate Balance Sheet without serializers
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Generate Balance Sheet
        """
        # Asset Accounts
        asset_types = [
            'cash', 'bank', 'accounts_receivable', 
            'inventory', 'fixed_assets', 'other_current_assets'
        ]
        
        assets = []
        total_assets = Decimal('0.00')
        
        for asset_type in asset_types:
            accounts = Account.objects.filter(account_type=asset_type, is_active=True)
            for account in accounts:
                asset_info = {
                    'name': account.name,
                    'code': account.code,
                    'balance': float(account.balance)
                }
                assets.append(asset_info)
                total_assets += account.balance
        
        # Liability Accounts
        liability_types = [
            'accounts_payable', 'credit_card', 
            'current_liabilities', 'long_term_liabilities'
        ]
        
        liabilities = []
        total_liabilities = Decimal('0.00')
        
        for liability_type in liability_types:
            accounts = Account.objects.filter(account_type=liability_type, is_active=True)
            for account in accounts:
                liability_info = {
                    'name': account.name,
                    'code': account.code,
                    'balance': float(account.balance)
                }
                liabilities.append(liability_info)
                total_liabilities += account.balance
        
        # Equity Accounts
        equity_types = [
            'owner_equity', 'retained_earnings'
        ]
        
        equity = []
        total_equity = Decimal('0.00')
        
        for equity_type in equity_types:
            accounts = Account.objects.filter(account_type=equity_type, is_active=True)
            for account in accounts:
                equity_info = {
                    'name': account.name,
                    'code': account.code,
                    'balance': float(account.balance)
                }
                equity.append(equity_info)
                total_equity += account.balance
        
        return JsonResponse({
            'assets': assets,
            'liabilities': liabilities,
            'equity': equity,
            'total_assets': float(total_assets),
            'total_liabilities': float(total_liabilities),
            'total_equity': float(total_equity)
        })


class ProfitLossStatementView(APIView):
    """
    API view to generate Profit and Loss Statement without serializers
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Generate Profit and Loss Statement
        """
        # Optional date range filtering
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        # Income Accounts
        income_types = [
            'sales_income', 'service_income', 'other_income'
        ]
        
        income = []
        total_income = Decimal('0.00')
        
        for income_type in income_types:
            accounts = Account.objects.filter(account_type=income_type, is_active=True)
            for account in accounts:
                # Calculate total income from transaction lines for this account
                # Apply date filtering if dates are provided
                income_query = TransactionLine.objects.filter(
                    account=account, 
                    transaction__transaction_type='income'
                )
                
                if start_date:
                    income_query = income_query.filter(transaction__date__gte=start_date)
                if end_date:
                    income_query = income_query.filter(transaction__date__lte=end_date)
                
                income_amount = income_query.aggregate(total=Sum('credit_amount'))['total'] or Decimal('0.00')
                
                income_info = {
                    'name': account.name,
                    'code': account.code,
                    'amount': float(income_amount)
                }
                income.append(income_info)
                total_income += income_amount
        
        # Expense Accounts
        expense_types = [
            'cost_of_goods_sold', 'operating_expenses', 
            'payroll_expenses', 'marketing_expenses', 
            'administrative_expenses', 'other_expenses'
        ]
        
        expenses = []
        total_expenses = Decimal('0.00')
        
        for expense_type in expense_types:
            accounts = Account.objects.filter(account_type=expense_type, is_active=True)
            for account in accounts:
                # Calculate total expenses from transaction lines for this account
                # Apply date filtering if dates are provided
                expense_query = TransactionLine.objects.filter(
                    account=account, 
                    transaction__transaction_type='expense'
                )
                
                if start_date:
                    expense_query = expense_query.filter(transaction__date__gte=start_date)
                if end_date:
                    expense_query = expense_query.filter(transaction__date__lte=end_date)
                
                expense_amount = expense_query.aggregate(total=Sum('debit_amount'))['total'] or Decimal('0.00')
                
                expense_info = {
                    'name': account.name,
                    'code': account.code,
                    'amount': float(expense_amount)
                }
                expenses.append(expense_info)
                total_expenses += expense_amount
        
        # Calculate Net Profit
        net_profit = total_income - total_expenses
        
        return JsonResponse({
            'income': income,
            'expenses': expenses,
            'total_income': float(total_income),
            'total_expenses': float(total_expenses),
            'net_profit': float(net_profit)
        })