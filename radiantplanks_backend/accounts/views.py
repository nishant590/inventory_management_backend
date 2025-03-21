from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Account, ReceivableTracking, Transaction, TransactionLine, PayableTracking, OwnerPaymentDetails
from django.core.exceptions import ValidationError
from django.db.models import Sum, Q
import io
from django.http import JsonResponse
from collections import defaultdict
from rest_framework.pagination import PageNumberPagination
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator, EmptyPage
from customers.models import Customer, Vendor
from rest_framework.permissions import IsAuthenticated
from decimal import Decimal
import pandas as pd
from radiantplanks_backend.logging import log
import traceback
from authentication.views import audit_log
from datetime import datetime, timedelta 
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils.timezone import now
from dateutil.relativedelta import relativedelta
from io import BytesIO
import math


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
            valid_account_types = ['cash',
                    'bank',
                    'accounts_receivable',
                    'inventory',
                    'fixed_assets',
                    'other_current_assets',
                    'accounts_payable',
                    'tax_payable',
                    'credit_card',
                    'current_liabilities',
                    'long_term_liabilities',
                    'owner_equity',
                    'retained_earnings',
                    'sales_income',
                    'service_income',
                    'other_income',
                    'cost_of_goods_sold',
                    'operating_expenses',
                    'payroll_expenses',
                    'marketing_expenses',
                    'administrative_expenses',
                    'other_expenses']
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
                              ip_add=request.META.get('HTTP_X_FORWARDED_FOR'), 
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
                "customer__business_name", "receivable_amount", "advance_payment"
            )
            
            # Convert the queryset to a pandas DataFrame
            df = pd.DataFrame.from_records(receivables, columns=["customer__business_name", "receivable_amount", "advance_payment"])
            
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
                              ip_add=request.META.get('HTTP_X_FORWARDED_FOR'), 
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
    

class AccountReceivablesSingleView(APIView):
    def get(self, request, customer_id):
        try:
            # Fetch data from the database directly as a queryset
            receivables = ReceivableTracking.objects.filter(customer=customer_id).values(
                "customer__business_name", "receivable_amount", "advance_payment"
            )
            
            # Convert the queryset to a pandas DataFrame
            df = pd.DataFrame.from_records(receivables, columns=["customer__business_name", "receivable_amount", "advance_payment"])
            
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
                              ip_add=request.META.get('HTTP_X_FORWARDED_FOR'), 
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


class AccountPayableView(APIView):
    def get(self, request):
        try:
            # Fetch data from the database directly as a queryset
            payables = PayableTracking.objects.values(
                "vendor__business_name", "payable_amount", "advance_payment"
            )
            
            # Convert the queryset to a pandas DataFrame
            df = pd.DataFrame.from_records(payables, columns=["vendor__business_name", "payable_amount", "advance_payment"])
            
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
                              ip_add=request.META.get('HTTP_X_FORWARDED_FOR'), 
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


class AccountPayableSingleView(APIView):
    def get(self, request, vendor_id):
        try:
            # Fetch data from the database directly as a queryset
            payables = PayableTracking.objects.filter(vendor=vendor_id).values(
                "vendor__business_name", "payable_amount", "advance_payment"
            )
            
            # Convert the queryset to a pandas DataFrame
            df = pd.DataFrame.from_records(payables, columns=["vendor__business_name", "payable_amount", "advance_payment"])
            
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
                              ip_add=request.META.get('HTTP_X_FORWARDED_FOR'), 
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
    permission_classes = [IsAuthenticated]

    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        try:
            if start_date:
                start_date = datetime.strptime(start_date, "%Y-%m-%d")
            if end_date:
                end_date = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)

        def calculate_balance(account, non_asset=False):
            if start_date and end_date:
                transaction_lines = TransactionLine.objects.filter(
                    account=account,
                    transaction__date__gte=start_date,
                    transaction__date__lte=end_date,
                    transaction__is_active=True,
                    is_active=True
                )
            else:
                transaction_lines = TransactionLine.objects.filter(
                    account=account,
                    transaction__is_active=True,
                    is_active=True
                )
            debit_sum = transaction_lines.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
            credit_sum = transaction_lines.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
            if non_asset:
                return_val = credit_sum - debit_sum
            else:
                return_val = debit_sum - credit_sum 
            return return_val

        # Asset Accounts
        asset_types = ['cash', 'bank', 'accounts_receivable', 'inventory', 'fixed_assets', 'other_current_assets']
        assets = []
        total_assets = Decimal('0.00')

        for asset_type in asset_types:
            accounts = Account.objects.filter(account_type=asset_type, is_active=True)
            for account in accounts:
                balance = calculate_balance(account)
                assets.append({
                    'name': account.name,
                    'code': account.code,
                    'balance': float(balance)
                })
                total_assets += balance

        # Liability Accounts
        liability_types = ['accounts_payable', 'credit_card', 'current_liabilities', 'long_term_liabilities', 'tax_payable']
        liabilities = []
        total_liabilities = Decimal('0.00')

        for liability_type in liability_types:
            accounts = Account.objects.filter(account_type=liability_type, is_active=True)
            for account in accounts:
                balance = calculate_balance(account, non_asset=True)
                liabilities.append({
                    'name': account.name,
                    'code': account.code,
                    'balance': float(balance)
                })
                total_liabilities += balance

        # Equity Accounts
        equity_types = ['owner_equity', 'retained_earnings']
        equity = []
        total_equity = Decimal('0.00')

        for equity_type in equity_types:
            accounts = Account.objects.filter(account_type=equity_type, is_active=True)
            for account in accounts:
                balance = calculate_balance(account, non_asset=True)
                equity.append({
                    'name': account.name,
                    'code': account.code,
                    'balance': float(balance)
                })
                total_equity += balance

        return JsonResponse({
            'assets': assets,
            'liabilities': liabilities,
            'equity': equity,
            'total_assets': float(total_assets),
            'total_liabilities': float(total_liabilities),
            'total_equity': float(total_equity)
        })


class CompareBalanceSheetView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        period1_start = request.query_params.get('period1_start')
        period1_end = request.query_params.get('period1_end')
        period2_start = request.query_params.get('period2_start')
        period2_end = request.query_params.get('period2_end')

        try:
            period1_start = datetime.strptime(period1_start, "%Y-%m-%d") if period1_start else None
            period1_end = datetime.strptime(period1_end, "%Y-%m-%d") if period1_end else None
            period2_start = datetime.strptime(period2_start, "%Y-%m-%d") if period2_start else None
            period2_end = datetime.strptime(period2_end, "%Y-%m-%d") if period2_end else None
        except ValueError:
            return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)

        def calculate_balance(account, start_date, end_date, non_asset=False):
            transaction_lines = TransactionLine.objects.filter(
                account=account,
                transaction__is_active=True,
                is_active=True
            )
            if start_date and end_date:
                transaction_lines = transaction_lines.filter(
                    transaction__date__gte=start_date,
                    transaction__date__lte=end_date
                )
            
            debit_sum = transaction_lines.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
            credit_sum = transaction_lines.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
            return credit_sum - debit_sum if non_asset else debit_sum - credit_sum

        def get_comparison_data(account_types, non_asset=False):
            comparison = []
            for account_type in account_types:
                accounts = Account.objects.filter(account_type=account_type, is_active=True)
                for account in accounts:
                    balance_period1 = calculate_balance(account, period1_start, period1_end, non_asset)
                    balance_period2 = calculate_balance(account, period2_start, period2_end, non_asset)
                    comparison.append({
                        'name': account.name,
                        'code': account.code,
                        'period1_balance': float(balance_period1),
                        'period2_balance': float(balance_period2),
                        'difference': float(balance_period2 - balance_period1)
                    })
            return comparison

        asset_types = ['cash', 'bank', 'accounts_receivable', 'inventory', 'fixed_assets', 'other_current_assets']
        liability_types = ['accounts_payable', 'credit_card', 'current_liabilities', 'long_term_liabilities', 'tax_payable']
        equity_types = ['owner_equity', 'retained_earnings']

        return JsonResponse({
            'assets': get_comparison_data(asset_types),
            'liabilities': get_comparison_data(liability_types, non_asset=True),
            'equity': get_comparison_data(equity_types, non_asset=True)
        })




class BalanceSheetXLSXView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        try:
            if start_date:
                start_date = datetime.strptime(start_date, "%Y-%m-%d")
            if end_date:
                end_date = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)

        def calculate_balance(account, non_asset=False):
            if start_date and end_date:
                transaction_lines = TransactionLine.objects.filter(
                    account=account,
                    transaction__date__gte=start_date,
                    transaction__date__lte=end_date,
                    transaction__is_active=True,
                    is_active=True
                )
            else:
                transaction_lines = TransactionLine.objects.filter(
                    account=account,
                    transaction__is_active=True,
                    is_active=True
                )
            debit_sum = transaction_lines.aggregate(Sum('debit_amount'))['debit_amount__sum'] or Decimal('0.00')
            credit_sum = transaction_lines.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
            if non_asset:
                return_val = credit_sum - debit_sum
            else:
                return_val = debit_sum - credit_sum 
            return return_val

        # Asset Accounts
        asset_types = ['cash', 'bank', 'accounts_receivable', 'inventory', 'fixed_assets', 'other_current_assets']
        assets = []
        total_assets = Decimal('0.00')
        assets.append({"name":"Assets","balance":None})
        for asset_type in asset_types:
            accounts = Account.objects.filter(account_type=asset_type, is_active=True)
            for account in accounts:
                balance = calculate_balance(account)
                assets.append({
                    'name': account.name,
                    'balance': float(balance)
                })
                total_assets += balance
        assets.append({"name":"Total Assets","balance":float(total_assets)})

        # Liability Accounts
        liability_types = ['accounts_payable', 'credit_card', 'current_liabilities', 'long_term_liabilities', 'tax_payable']
        liabilities = []
        total_liabilities = Decimal('0.00')
        liabilities.append({"name":"Liabilities","balance":None})
        for liability_type in liability_types:
            accounts = Account.objects.filter(account_type=liability_type, is_active=True)
            for account in accounts:
                balance = calculate_balance(account, non_asset=True)
                liabilities.append({
                    'name': account.name,
                    'balance': float(balance)
                })
                total_liabilities += balance
        liabilities.append({"name":"Total Liabilities","balance":float(total_liabilities)})

        # Equity Accounts
        equity_types = ['owner_equity', 'retained_earnings']
        equity = []
        total_equity = Decimal('0.00')

        equity.append({"name":"Equity","balance":None})
        for equity_type in equity_types:
            accounts = Account.objects.filter(account_type=equity_type, is_active=True)
            for account in accounts:
                balance = calculate_balance(account, non_asset=True)
                equity.append({
                    'name': account.name,
                    'balance': float(balance)
                })
                total_equity += balance
        equity.append({"name":"Total Equity","balance":float(total_equity)})

        final_data = assets + liabilities + equity
        df = pd.DataFrame(final_data)

        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=balance_sheet.xlsx'
        
        with pd.ExcelWriter(response, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Profit & Loss Statement', index=False)
            writer.close()
        
        return response


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
        # customer_id = request.GET.get('customer_id')
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
                    transaction__transaction_type='income',
                    is_active=True
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
                    is_active=True
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
    

class ProfitLossComparisonView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        period_type = request.GET.get('period_type', 'monthly')  # Options: monthly, quarterly, yearly
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        if not start_date or not end_date:
            return JsonResponse({'error': 'start_date and end_date are required'}, status=400)
        
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        
        period_ranges = self.generate_periods(start_date, end_date, period_type)
        
        report = []
        for period_start, period_end in period_ranges:
            report.append(self.generate_detailed_pnl_statement(period_start, period_end))
        
        return JsonResponse({'report': report})
    
    def generate_periods(self, start_date, end_date, period_type):
        periods = []
        current_start = start_date
        
        while current_start <= end_date:
            if period_type == 'monthly':
                next_start = current_start + relativedelta(months=1)
            elif period_type == 'quarterly':
                next_start = current_start + relativedelta(months=3)
            elif period_type == 'yearly':
                next_start = current_start + relativedelta(years=1)
            else:
                raise ValueError("Invalid period type")
            
            period_end = min(next_start - timedelta(days=1), end_date)
            periods.append((current_start, period_end))
            current_start = next_start
        
        return periods
    
    def generate_detailed_pnl_statement(self, start_date, end_date):
        income_types = ['sales_income', 'service_income', 'other_income']
        expense_types = ['cost_of_goods_sold', 'operating_expenses', 'payroll_expenses', 'marketing_expenses', 'administrative_expenses', 'other_expenses']
        
        total_income = Decimal('0.00')
        total_expenses = Decimal('0.00')
        income_details = []
        expense_details = []
        
        # Calculate Income
        for income_type in income_types:
            accounts = Account.objects.filter(account_type=income_type, is_active=True)
            for account in accounts:
                income_amount = TransactionLine.objects.filter(
                    account=account,
                    transaction__transaction_type='income',
                    transaction__date__gte=start_date,
                    transaction__date__lte=end_date,
                    is_active=True
                ).aggregate(total=Sum('credit_amount'))['total'] or Decimal('0.00')
                total_income += income_amount
                income_details.append({
                    'name': account.name,
                    'code': account.code,
                    'amount': float(income_amount)
                })
        
        # Calculate Expenses
        for expense_type in expense_types:
            accounts = Account.objects.filter(account_type=expense_type, is_active=True)
            for account in accounts:
                expense_amount = TransactionLine.objects.filter(
                    account=account,
                    transaction__date__gte=start_date,
                    transaction__date__lte=end_date,
                    is_active=True
                ).aggregate(total=Sum('debit_amount'))['total'] or Decimal('0.00')
                total_expenses += expense_amount
                expense_details.append({
                    'name': account.name,
                    'code': account.code,
                    'amount': float(expense_amount)
                })
        
        return {
            'start_date': str(start_date),
            'end_date': str(end_date),
            'income': income_details,
            'expenses': expense_details,
            'total_income': float(total_income),
            'total_expenses': float(total_expenses),
            'net_profit': float(total_income - total_expenses)
        }


class ProfitLossComparisonAccrualView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        period_type = request.GET.get('period_type', 'monthly')  # Options: monthly, quarterly, yearly
        report_type = request.GET.get('report_type', 'accrual')  # Options: accrual, cash
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        if not start_date or not end_date:
            return JsonResponse({'error': 'start_date and end_date are required'}, status=400)
        
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        
        period_ranges = self.generate_periods(start_date, end_date, period_type)
        
        report = []
        for period_start, period_end in period_ranges:
            report.append(self.generate_detailed_pnl_statement(period_start, period_end, report_type))
        
        return JsonResponse({'report': report})
    
    def generate_periods(self, start_date, end_date, period_type):
        periods = []
        current_start = start_date
        
        while current_start <= end_date:
            if period_type == 'monthly':
                next_start = current_start + relativedelta(months=1)
            elif period_type == 'quarterly':
                next_start = current_start + relativedelta(months=3)
            elif period_type == 'yearly':
                next_start = current_start + relativedelta(years=1)
            else:
                raise ValueError("Invalid period type")
            
            period_end = min(next_start - timedelta(days=1), end_date)
            periods.append((current_start, period_end))
            current_start = next_start
        
        return periods
    
    def generate_detailed_pnl_statement(self, start_date, end_date, report_type):
        income_types = ['sales_income', 'service_income', 'other_income']
        expense_types = ['cost_of_goods_sold', 'operating_expenses', 'payroll_expenses', 'marketing_expenses', 'administrative_expenses', 'other_expenses']
        
        total_income = Decimal('0.00')
        total_expenses = Decimal('0.00')
        income_details = []
        expense_details = []
        
        # Calculate Income
        for income_type in income_types:
            accounts = Account.objects.filter(account_type=income_type, is_active=True)
            for account in accounts:
                income_query = TransactionLine.objects.filter(
                    account=account,
                    transaction__transaction_type='income',
                    transaction__date__gte=start_date,
                    transaction__date__lte=end_date,
                    is_active=True
                )
                
                if report_type == 'cash':
                    income_query = income_query.filter(transaction__invoice_transactions__is_payment_transaction=True)
                else:
                    income_query = income_query.filter(transaction__invoice_transactions__is_payment_transaction=False)
                
                income_amount = income_query.aggregate(total=Sum('credit_amount'))['total'] or Decimal('0.00')
                total_income += income_amount
                income_details.append({
                    'name': account.name,
                    'code': account.code,
                    'amount': float(income_amount)
                })
        
        # Calculate Expenses
        for expense_type in expense_types:
            accounts = Account.objects.filter(account_type=expense_type, is_active=True)
            for account in accounts:
                expense_query = TransactionLine.objects.filter(
                    account=account,
                    transaction__date__gte=start_date,
                    transaction__date__lte=end_date,
                    is_active=True
                )
                
                if report_type == 'cash':
                    expense_query = expense_query.filter(account__account_type__in=['cash', 'bank'])
                
                expense_amount = expense_query.aggregate(total=Sum('debit_amount'))['total'] or Decimal('0.00')
                total_expenses += expense_amount
                expense_details.append({
                    'name': account.name,
                    'code': account.code,
                    'amount': float(expense_amount)
                })
        
        return {
            'start_date': str(start_date),
            'end_date': str(end_date),
            'report_type': report_type,
            'income': income_details,
            'expenses': expense_details,
            'total_income': float(total_income),
            'total_expenses': float(total_expenses),
            'net_profit': float(total_income - total_expenses)
        }



class ProfitLossStatementCustomerView(APIView):
    """
    API view to generate Profit and Loss Statement for a specific customer
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Generate Profit and Loss Statement
        """
        # Optional filtering by customer and date range
        customer_id = request.GET.get('customer_id')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        if not customer_id:
            return JsonResponse({'error': 'customer_id is required'}, status=400)
        
        try:
            customer = Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            return JsonResponse({'error': 'Customer not found'}, status=404)

        # Income Accounts
        income_types = ['sales_income', 'service_income', 'other_income']
        income = []
        total_income = Decimal('0.00')

        for income_type in income_types:
            accounts = Account.objects.filter(account_type=income_type, is_active=True)
            for account in accounts:
                # Calculate total income from transaction lines for this account and customer
                income_query = TransactionLine.objects.filter(
                    account=account,
                    transaction__transaction_type='income',
                    transaction__payment_details__customer=customer,
                    is_active=True 
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
                # Calculate total expenses from transaction lines for this account and customer
                expense_query = TransactionLine.objects.filter(
                    account=account,
                    transaction__transaction_type='expense',
                    transaction__payment_details__customer=customer,
                    is_active=True 
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
            'customer': {
                'id': customer.customer_id,
                'name': customer.business_name
            },
            'income': income,
            'expenses': expenses,
            'total_income': float(total_income),
            'total_expenses': float(total_expenses),
            'net_profit': float(net_profit)
        })


class ProfitLossXLSXView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')

        # Income Accounts
        income_types = [
            'sales_income', 'service_income', 'other_income'
        ]
        
        income = []
        total_income = Decimal('0.00')
        income.append({"name":"Income","amount":None})
        for income_type in income_types:
            accounts = Account.objects.filter(account_type=income_type, is_active=True)
            for account in accounts:
                # Calculate total income from transaction lines for this account
                # Apply date filtering if dates are provided
                income_query = TransactionLine.objects.filter(
                    account=account, 
                    transaction__transaction_type='income',
                    is_active=True
                )
                
                if start_date:
                    income_query = income_query.filter(transaction__date__gte=start_date)
                if end_date:
                    income_query = income_query.filter(transaction__date__lte=end_date)
                
                income_amount = income_query.aggregate(total=Sum('credit_amount'))['total'] or Decimal('0.00')
                
                income_info = {
                    'name': account.name,
                    'amount': round(float(income_amount),2)
                }
                income.append(income_info)
                total_income += income_amount
        income.append({"name":"Total","amount":round(float(total_income),2)})
        
        # Expense Accounts
        expense_types = [
            'cost_of_goods_sold', 'operating_expenses', 
            'payroll_expenses', 'marketing_expenses', 
            'administrative_expenses', 'other_expenses'
        ]
        
        expenses = []
        total_expenses = Decimal('0.00')
        expenses.append({"name":"Expenses","amount":None})
        for expense_type in expense_types:
            accounts = Account.objects.filter(account_type=expense_type, is_active=True)
            for account in accounts:
                # Calculate total expenses from transaction lines for this account
                # Apply date filtering if dates are provided
                expense_query = TransactionLine.objects.filter(
                    account=account, 
                    is_active=True
                )
                
                if start_date:
                    expense_query = expense_query.filter(transaction__date__gte=start_date)
                if end_date:
                    expense_query = expense_query.filter(transaction__date__lte=end_date)
                
                expense_amount = expense_query.aggregate(total=Sum('debit_amount'))['total'] or Decimal('0.00')
                
                expense_info = {
                    'name': account.name,
                    'amount': round(float(expense_amount),2)
                }
                expenses.append(expense_info)
                total_expenses += expense_amount
        expenses.append({"name":"Total","amount":round(float(total_expenses),2)})

        gross_profit = total_income - total_expenses
        income += expenses
        income.append({"name":"Gross Profit","amount":round(float(gross_profit),2)})
        
        df = pd.DataFrame(income)
        
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=profit_loss_statement.xlsx'
        
        with pd.ExcelWriter(response, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Profit & Loss Statement', index=False)
            writer.close()
        
        return response


class ProfitLossComparisonXLSXView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        period_type = request.GET.get('period_type', 'monthly')  # Options: monthly, quarterly, yearly
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        if not start_date or not end_date:
            return JsonResponse({'error': 'start_date and end_date are required'}, status=400)
        
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        
        period_ranges = self.generate_periods(start_date, end_date, period_type)
        
        report = []
        for period_start, period_end in period_ranges:
            report.append(self.generate_detailed_pnl_statement(period_start, period_end))


        df = self.convert_to_dataframe(report)
        
        # Export to Excel
        return self.export_to_excel(df)
    
    def generate_periods(self, start_date, end_date, period_type):
        periods = []
        current_start = start_date
        
        while current_start <= end_date:
            if period_type == 'monthly':
                next_start = current_start + relativedelta(months=1)
            elif period_type == 'quarterly':
                next_start = current_start + relativedelta(months=3)
            elif period_type == 'yearly':
                next_start = current_start + relativedelta(years=1)
            else:
                raise ValueError("Invalid period type")
            
            period_end = min(next_start - timedelta(days=1), end_date)
            periods.append((current_start, period_end))
            current_start = next_start
        
        return periods
    
    def generate_detailed_pnl_statement(self, start_date, end_date):
        income_types = ['sales_income', 'service_income', 'other_income']
        expense_types = ['cost_of_goods_sold', 'operating_expenses', 'payroll_expenses', 'marketing_expenses', 'administrative_expenses', 'other_expenses']
        
        total_income = Decimal('0.00')
        total_expenses = Decimal('0.00')
        income_details = []
        expense_details = []
        
        # Calculate Income
        for income_type in income_types:
            accounts = Account.objects.filter(account_type=income_type, is_active=True)
            for account in accounts:
                income_amount = TransactionLine.objects.filter(
                    account=account,
                    transaction__transaction_type='income',
                    transaction__date__gte=start_date,
                    transaction__date__lte=end_date,
                    is_active=True
                ).aggregate(total=Sum('credit_amount'))['total'] or Decimal('0.00')
                total_income += income_amount
                income_details.append({
                    'name': account.name,
                    'code': account.code,
                    'amount': float(income_amount)
                })
        
        # Calculate Expenses
        for expense_type in expense_types:
            accounts = Account.objects.filter(account_type=expense_type, is_active=True)
            for account in accounts:
                expense_amount = TransactionLine.objects.filter(
                    account=account,
                    transaction__date__gte=start_date,
                    transaction__date__lte=end_date,
                    is_active=True
                ).aggregate(total=Sum('debit_amount'))['total'] or Decimal('0.00')
                total_expenses += expense_amount
                expense_details.append({
                    'name': account.name,
                    'code': account.code,
                    'amount': float(expense_amount)
                })
        
        return {
            'start_date': str(start_date),
            'end_date': str(end_date),
            'income': income_details,
            'expenses': expense_details,
            'total_income': float(total_income),
            'total_expenses': float(total_expenses),
            'net_profit': float(total_income - total_expenses)
        }
    
    def convert_to_dataframe(self, input_data):
        # Initialize lists to store data
        main_income_df = pd.DataFrame()
        main_expenses_df = pd.DataFrame()

        # Process each report entry
        for entry in input_data:
            income_data = []
            expenses_data = []
            period_label = f"{entry['start_date']} – {entry['end_date']}"

            # Process income
            for income in entry["income"]:
                income_data.append({
                    "Account": income["name"],
                    "Type": "Income",
                    period_label: income["amount"]
                })

            # Process expenses
            for expense in entry["expenses"]:
                expenses_data.append({
                    "Account": expense["name"],
                    "Type": "Expenses",
                    period_label: expense["amount"]
                })

            income_df = pd.DataFrame(income_data)
            expenses_df = pd.DataFrame(expenses_data)
            if main_income_df.empty:
                main_income_df = income_df
            else:
                main_income_df = pd.merge(main_income_df, income_df, on=["Account", "Type"], how="outer")
            if main_expenses_df.empty:
                main_expenses_df = expenses_df
            else:
                main_expenses_df = pd.merge(main_expenses_df, expenses_df, on=["Account", "Type"], how="outer")

        # Combine income and expenses
        combined_df = pd.concat([main_income_df, main_expenses_df])

        # Fill missing values with 0
        combined_df = combined_df.fillna(0)
            # Calculate Net Profit
        numeric_cols = combined_df.columns[2:]  # Skip 'Account' and 'Type'
        total_income = combined_df[combined_df["Type"] == "Income"][numeric_cols].sum()
        total_expenses = combined_df[combined_df["Type"] == "Expenses"][numeric_cols].sum()
        net_profit = total_income - total_expenses

        # Append net profit row
        net_profit_row = pd.DataFrame([["Net Profit", "Total"] + net_profit.tolist()], columns=combined_df.columns)
        combined_df = pd.concat([combined_df, net_profit_row], ignore_index=True)

        return combined_df

    def export_to_excel(self, df):
        # Create HTTP response
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=profit_loss_comparison.xlsx'

        # Write DataFrame to Excel
        with pd.ExcelWriter(response, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Profit & Loss Statement', index=False)

        return response    
    
    

class AccountsReceivableAPIView(APIView):
    """
    Retrieve total Accounts Receivable for a specific date range
    """
    def get(self, request):
        try:
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')


            receivable_account = Account.objects.filter(account_type='accounts_receivable')
            receivables = TransactionLine.objects.filter(
                transaction__date__range=[start_date, end_date],
                account__in=receivable_account,
                is_active=True
            ).aggregate(total_receivable=Sum('debit_amount') - Sum('credit_amount'))
                
            return Response({"total_receivable": receivables['total_receivable'] or 0}, status=status.HTTP_200_OK)
        except Exception as e:
            log.trace.trace(f"Error getting receivables {traceback.format_exc()}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AccountsPayableAPIView(APIView):
    """
    Retrieve total Accounts Payable for a specific date range
    """
    def get(self, request):
        try:
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')


            payable_account = Account.objects.filter(account_type='accounts_payable')
            payables = TransactionLine.objects.filter(
                transaction__date__range=[start_date, end_date],
                account__in=payable_account,
                is_active=True
            ).aggregate(total_payable=Sum('credit_amount') - Sum('debit_amount'))

            return Response({"total_payable": payables['total_payable'] or 0}, status=status.HTTP_200_OK)
        except Exception as e:
            log.trace.trace(f"Error getting payables {traceback.format_exc()}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OwnerContributionAPI(APIView):
    def post(self, request):
        data = request.data
        try:
            amount = Decimal(data.get('amount', 0))
            source_account_code = data.get('source_account')  # e.g., 'cash' or 'bank'
            description = data.get('description', 'Owner Contribution')
            contribution_date = data.get('date', now().date())
            transaction_reference = data.get('transaction_reference', None)
            payment_method = data.get('payment_method', 'cash')


            if amount <= 0: 
                return Response({"error": "Amount must be greater than zero."}, status=status.HTTP_400_BAD_REQUEST)

            # Fetch accounts
            source_account = get_object_or_404(Account, code=source_account_code, is_active=True)
            owner_equity_account = get_object_or_404(Account, code='OWN-001', is_active=True)

            with transaction.atomic():
                # Create the transaction
                transaction_entry = Transaction.objects.create(
                    reference_number=f"OC-{Transaction.objects.count() + 1}",
                    transaction_type='journal',
                    date=contribution_date,
                    description=description,
                    created_by=request.user,
                )

                # Create transaction lines
                TransactionLine.objects.create(
                    transaction=transaction_entry,
                    account=source_account,
                    debit_amount=amount,
                    credit_amount=0,
                    description=f"Debit {description}"
                )
                TransactionLine.objects.create(
                    transaction=transaction_entry,
                    account=owner_equity_account,
                    debit_amount=0,
                    credit_amount=amount,
                    description=f"Credit {description}"
                )

                owner_entry = OwnerPaymentDetails.objects.create(
                    transaction=transaction_entry,
                    transaction_type='money_added',
                    description=description,
                    transaction_reference_id=transaction_reference,
                    payment_method=payment_method,
                    payment_amount=amount,
                    money_flag=1,
                    payment_date=contribution_date)

                # Update account balances
                source_account.balance += amount
                source_account.save()

                owner_equity_account.balance += amount
                owner_equity_account.save()

            audit_log_entry = audit_log(user=request.user,
                              action="Owner Contribution recorded", 
                              ip_add=request.META.get('HTTP_X_FORWARDED_FOR'), 
                              model_name="OwnerPaymentDetails", 
                              record_id=owner_entry.id)

            return Response({
                "message": "Owner contribution recorded successfully.",
                "transaction_id": transaction_entry.id,
                "source_account_balance": source_account.balance,
                "owner_equity_balance": owner_equity_account.balance
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class GetAllOwnerTransactionsAPI(APIView):
    def get(self, request):
        # Fetch all owner transactions
        transactions = OwnerPaymentDetails.objects.all()
        transaction_data = []

        for transaction in transactions:
            # Fetch the associated transaction
            try:
                transaction_obj = Transaction.objects.get(id=transaction.transaction.id)
            except Transaction.DoesNotExist:
                continue  # Skip if no associated transaction exists

            # Fetch transaction lines for the transaction
            transaction_lines = TransactionLine.objects.filter(transaction=transaction_obj)

            # Find the account where money was added (credit amount > 0)
            credited_account = None
            for line in transaction_lines:
                if line.account.code != "OWN-001":
                    credited_account = line.account
                    break  # Assuming only one account is credited per transaction

            # Append transaction data with credited account information
            transaction_data.append({
                'id': transaction.id,
                'amount': transaction.payment_amount,
                'transaction_type': transaction.transaction_type,
                'description': transaction.description,
                'transaction_reference_id': transaction.transaction_reference_id,
                'payment_method': transaction.payment_method,
                'payment_date': transaction.payment_date,
                'money_flag': transaction.money_flag, 
                'credited_account': {
                    'id': credited_account.id if credited_account else None,
                    'name': credited_account.name if credited_account else None,
                    'account_number': credited_account.code if credited_account else None,
                },
                # Add other fields as needed
            })

        return Response(transaction_data)    


class OwnerTakeOutMoneyAPI(APIView):
    def post(self, request):
        data = request.data
        try:
            amount = Decimal(data.get('amount', 0))
            destination_account_code = data.get('destination_account')  # e.g., 'cash' or 'bank'
            description = data.get('description', 'Owner Money Withdrawal')
            withdrawal_date = data.get('date', now().date())
            transaction_reference = data.get('transaction_reference', None)
            payment_method = data.get('payment_method', 'cash')

            if amount <= 0:
                return Response({"error": "Amount must be greater than zero."}, status=status.HTTP_400_BAD_REQUEST)

            # Fetch accounts
            owner_equity_account = get_object_or_404(Account, code='OWN-001', is_active=True)
            destination_account = get_object_or_404(Account, code=destination_account_code, is_active=True)

            if owner_equity_account.balance < amount:
                return Response({"error": "Insufficient funds in owner equity account."}, status=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                # Create the transaction
                transaction_entry = Transaction.objects.create(
                    reference_number=f"OW-{Transaction.objects.count() + 1}",
                    transaction_type='journal',
                    date=withdrawal_date,
                    description=description,
                    created_by=request.user,
                )

                # Create transaction lines
                TransactionLine.objects.create(
                    transaction=transaction_entry,
                    account=owner_equity_account,
                    debit_amount=amount,
                    credit_amount=0,
                    description=f"Debit {description}"
                )
                TransactionLine.objects.create(
                    transaction=transaction_entry,
                    account=destination_account,
                    debit_amount=0,
                    credit_amount=amount,
                    description=f"Credit {description}"
                )

                owner_entry = OwnerPaymentDetails.objects.create(
                    transaction=transaction_entry,
                    transaction_type='money_removed',
                    description=description,
                    transaction_reference_id=transaction_reference,
                    payment_method=payment_method,
                    payment_amount=amount,
                    money_flag=0,
                    payment_date=withdrawal_date)

                # Update account balances
                owner_equity_account.balance -= amount
                owner_equity_account.save()

                destination_account.balance -= amount
                destination_account.save()

            audit_log_entry = audit_log(user=request.user,
                              action="Owner Money Withdrawal recorded", 
                              ip_add=request.META.get('HTTP_X_FORWARDED_FOR'), 
                              model_name="OwnerPaymentDetails", 
                              record_id=owner_entry.id)

            return Response({
                "message": "Owner money withdrawal recorded successfully.",
                "transaction_id": transaction_entry.id,
                "source_account_balance": owner_equity_account.balance,
                "destination_account_balance": destination_account.balance
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        

class EditOwnerTransactionAPI(APIView):
    def put(self, request, id):
        data = request.data
        try:
            amount = Decimal(data.get('amount', 0))
            source_account_code = data.get('source_account')  # e.g., 'cash' or 'bank'
            description = data.get('description', 'Owner Contribution')
            contribution_date = data.get('date', datetime.now().date())
            transaction_reference = data.get('transaction_reference', None)
            payment_method = data.get('payment_method', 'cash')

            if amount <= 0:
                return Response({"error": "Amount must be greater than zero."}, status=status.HTTP_400_BAD_REQUEST)
            
            owner_entry = OwnerPaymentDetails.objects.filter(id=id).first()

            # Fetch the existing transaction
            transaction_entry = get_object_or_404(Transaction, id=owner_entry.transaction.id)
            old_transaction_lines = TransactionLine.objects.filter(transaction=transaction_entry, is_active=True).all()

            # Fetch accounts
            old_transaction_source_account = None
            for transaction_line in old_transaction_lines:
                if transaction_line.account.code != 'OWN-001':
                    old_transaction_source_account = transaction_line.account
                    break
            # if old_transaction_source_account.code == source_account_code: 
            owner_equity_account = get_object_or_404(Account, code='OWN-001', is_active=True)

            with transaction.atomic():
                # Set existing transaction lines to inactive

                if owner_entry:
                        owner_entry.description = description
                        owner_entry.transaction_reference_id = transaction_reference
                        owner_entry.payment_method = payment_method
                        owner_entry.payment_amount = amount
                        owner_entry.payment_date = contribution_date
                        owner_entry.save()

                # Update the transaction details
                transaction_entry.date = contribution_date
                transaction_entry.description = description
                transaction_entry.save()

                for line in old_transaction_lines:
                    if line.account == old_transaction_source_account:
                        if owner_entry.transaction_type == "money_added":
                            old_transaction_source_account.balance -= line.debit_amount
                            old_transaction_source_account.save()
                        if owner_entry.transaction_type == "money_removed":
                            old_transaction_source_account.balance += line.debit_amount
                            old_transaction_source_account.save()
                    elif line.account == owner_equity_account:
                        if owner_entry.transaction_type == "money_added":
                            owner_equity_account.balance -= line.credit_amount
                        if owner_entry.transaction_type == "money_removed":
                            owner_equity_account.balance += line.credit_amount
                        

                old_transaction_lines.update(is_active=False)
                # Create new transaction lines
                source_account = get_object_or_404(Account, code=source_account_code, is_active=True)
                if owner_entry.transaction_type == "money_added":
                    TransactionLine.objects.create(
                        transaction=transaction_entry,
                        account=source_account,
                        debit_amount=amount,
                        credit_amount=0,
                        description=f"Debit {description}"
                    )
                    TransactionLine.objects.create(
                        transaction=transaction_entry,
                        account=owner_equity_account,
                        debit_amount=0,
                        credit_amount=amount,
                        description=f"Credit {description}"
                    )
                elif owner_entry.transaction_type == "money_removed":
                    TransactionLine.objects.create(
                        transaction=transaction_entry,
                        account=source_account,
                        debit_amount=0,
                        credit_amount=amount,
                        description=f"Credit {description}"
                    )
                    TransactionLine.objects.create(
                        transaction=transaction_entry,
                        account=owner_equity_account,
                        debit_amount=amount,
                        credit_amount=0,
                        description=f"Debit {description}"
                    )
                # Update OwnerPaymentDetails if necessary

                # Update account balances
                # Subtract the old amounts from the account balances

                # Add the new amounts to the account balances
                if owner_entry.transaction_type == "money_added":
                    source_account.balance += amount
                    owner_equity_account.balance += amount
                if owner_entry.transaction_type == "money_removed":
                    source_account.balance -= amount
                    owner_equity_account.balance -= amount

                source_account.save()
                owner_equity_account.save()

            audit_log_entry = audit_log(user=request.user,
                              action="Transaction updated", 
                              ip_add=request.META.get('HTTP_X_FORWARDED_FOR'), 
                              model_name="Transaction", 
                              record_id=transaction_entry.id)

            return Response({
                "message": "Transaction updated successfully.",
                "transaction_id": transaction_entry.id,
                "source_account_balance": source_account.balance,
                "owner_equity_balance": owner_equity_account.balance
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        

class DeleteOwnerTransactionAPI(APIView):
    def delete(self, request, id):
        try:
            owner_entry = get_object_or_404(OwnerPaymentDetails, id=id)
            transaction_entry = get_object_or_404(Transaction, id=owner_entry.transaction.id)
            transaction_lines = TransactionLine.objects.filter(transaction=transaction_entry, is_active=True)

            owner_equity_account = get_object_or_404(Account, code='OWN-001', is_active=True)
            source_account = None

            for line in transaction_lines:
                if line.account.code != 'OWN-001':
                    source_account = line.account
                    break

            with transaction.atomic():
                # Reverse balances before deletion
                for line in transaction_lines:
                    if line.account == source_account:
                        if owner_entry.transaction_type == "money_added":
                            source_account.balance -= line.debit_amount
                        if owner_entry.transaction_type == "money_removed":
                            source_account.balance += line.credit_amount
                    elif line.account == owner_equity_account:
                        if owner_entry.transaction_type == "money_added":
                            owner_equity_account.balance -= line.credit_amount
                        if owner_entry.transaction_type == "money_removed":
                            owner_equity_account.balance += line.debit_amount
                
                source_account.save()
                owner_equity_account.save()

                # Set transaction lines to inactive
                transaction_lines.update(is_active=False)

                # Delete owner entry and transaction
                owner_entry.delete()
                transaction_entry.delete()

            audit_log_entry = audit_log(
                user=request.user,
                action="Transaction deleted",
                ip_add=request.META.get('HTTP_X_FORWARDED_FOR'),
                model_name="Transaction",
                record_id=id
            )
            log.app.info(f"Transaction deleted successfully: {id}")
            return Response({"message": "Transaction deleted successfully."}, status=status.HTTP_200_OK)

        except Exception as e:
            log.trace.trace(f"Error deleting transaction {traceback.format_exc()}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CustomPagination(PageNumberPagination):
    page_size = 10  # Default page size
    page_size_query_param = 'page_size'  # Allow client to override the page size
    max_page_size = 100  # Maximum page size


class TransactionListView(APIView):
    def get(self, request):
        # Fetch all transactions sorted by date and created_at in descending order
        transactions = Transaction.objects.all().order_by('-date', '-created_at')

        # Paginate the transactions
        paginator = CustomPagination()
        paginated_transactions = paginator.paginate_queryset(transactions, request)

        # Construct the response data
        response_data = []
        for transaction in paginated_transactions:
            # Fetch related OwnerPaymentDetails for the transaction
            owner_payment_details = OwnerPaymentDetails.objects.filter(transaction=transaction).first()

            # Build the transaction dictionary
            transaction_data = {
                'id': transaction.id,
                'reference_number': transaction.reference_number,
                'transaction_type': transaction.transaction_type,
                'date': transaction.date,
                'description': transaction.description,
                'is_reconciled': transaction.is_reconciled,
                'tax_amount': str(transaction.tax_amount),  # Convert Decimal to string for JSON serialization
                'attachment': transaction.attachment,
                'is_active': transaction.is_active,
                'created_by': transaction.created_by.id,  # Assuming created_by is a ForeignKey
                'created_at': transaction.created_at,
                'updated_at': transaction.updated_at,
                'owner_payment_details': None,
            }

            # Add OwnerPaymentDetails if it exists
            if owner_payment_details:
                transaction_data['owner_payment_details'] = {
                    'id': owner_payment_details.id,
                    'transaction_type': owner_payment_details.transaction_type,
                    'description': owner_payment_details.description,
                    'payment_method': owner_payment_details.payment_method,
                    'transaction_reference_id': owner_payment_details.transaction_reference_id,
                    'payment_amount': str(owner_payment_details.payment_amount),  # Convert Decimal to string
                    'payment_date': owner_payment_details.payment_date,
                }

            response_data.append(transaction_data)

        # Return the paginated response
        return paginator.get_paginated_response(response_data)
    


class BankAccountTransactionsAPIView(APIView):
    def get(self, request, *args, **kwargs):
        # Get the account_id and pagination parameters from query parameters
        account_id = request.GET.get('account_id', None)
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        # Simple pagination parameters
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))
        
        if not account_id:
            return Response(
                {"error": "account_id is required as a query parameter."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Fetch transactions that have at least one TransactionLine linked to the specified account
        transactions = Transaction.objects.filter(lines__account_id=account_id, is_active=True).distinct()
        
        if start_date and end_date:
            transactions = transactions.filter(date__range=[start_date, end_date])
        
        # Get total count for pagination
        total_count = transactions.count()
        total_pages = math.ceil(total_count / page_size)
        
        # Manual pagination
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        paginated_transactions = transactions[start_index:end_index]
        
        # Build pagination metadata
        pagination_info = {
            "total_count": total_count,
            "total_pages": total_pages,
            "current_page": page,
            "page_size": page_size,
            "has_next": page < total_pages,
            "has_previous": page > 1
        }
        
        # Prepare the response data
        response_data = []
        for transaction in paginated_transactions:
            # Fetch transaction lines for the current transaction and the specified account
            transaction_lines = TransactionLine.objects.filter(transaction=transaction, account_id=account_id, is_active=True)
            
            # Build the transaction data
            transaction_data = {
                "id": transaction.id,
                "reference_number": transaction.reference_number,
                "transaction_type": transaction.transaction_type,
                "date": transaction.date,
                "description": transaction.description,
                "lines": []
            }
            
            # Add transaction lines to the transaction data
            for line in transaction_lines:
                transaction_data["lines"].append({
                    "id": line.id,
                    "account": line.account.id,
                    "description": line.description,
                    "debit_amount": str(line.debit_amount),  # Convert Decimal to string
                    "credit_amount": str(line.credit_amount),  # Convert Decimal to string
                    "invoice_id": line.invoice_id,
                    "bill_id": line.bill_id,
                    "is_active": line.is_active
                })
                
            # Add the transaction data to the response
            response_data.append(transaction_data)
            
        # Return the response with pagination metadata
        return Response({
            "pagination": pagination_info,
            "data": response_data
        }, status=status.HTTP_200_OK)


class BankAccountTransactionsExportAPIView(APIView):
    def get(self, request, *args, **kwargs):
        # Get the account_id from query parameters
        account_id = request.GET.get('account_id', None)
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        if not account_id:
            return Response(
                {"error": "account_id is required as a query parameter."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Fetch transactions that have at least one TransactionLine linked to the specified account
        transactions = Transaction.objects.filter(lines__account_id=account_id, is_active=True).distinct()
        
        if start_date and end_date:
            transactions = transactions.filter(date__range=[start_date, end_date])
        
        # Prepare data for pandas DataFrame
        data = []
        for transaction in transactions:
            # Fetch transaction lines for the current transaction and the specified account
            transaction_lines = TransactionLine.objects.filter(transaction=transaction, account_id=account_id, is_active=True)
            
            for line in transaction_lines:
                data.append({
                    'Transaction ID': transaction.id,
                    'Reference Number': transaction.reference_number,
                    'Transaction Type': transaction.transaction_type,
                    'Date': transaction.date,
                    'Description': transaction.description,
                    'Line ID': line.id,
                    'Account': line.account.id,
                    'Line Description': line.description,
                    'Debit Amount': float(line.debit_amount) if line.debit_amount else 0,
                    'Credit Amount': float(line.credit_amount) if line.credit_amount else 0,
                })
        
        # Create DataFrame from data
        df = pd.DataFrame(data)
        
        # Generate Excel file
        output = BytesIO()
        
        # Create a Pandas Excel writer using BytesIO as the target
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Transactions', index=False)
            
            # Get the xlsxwriter workbook and worksheet objects
            workbook = writer.book
            worksheet = writer.sheets['Transactions']
            
            # Add some formatting
            header_format = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1})
            
            # Write the column headers with the defined format
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
                
            # Adjust column widths
            for i, col in enumerate(df.columns):
                # Set column width based on max length in column
                max_len = max(df[col].astype(str).apply(len).max(), len(str(col))) + 2
                worksheet.set_column(i, i, max_len)
        
        # Generate filename with account_id and date range
        filename = f"transactions_account_{account_id}"
        if start_date and end_date:
            filename += f"_{start_date}_to_{end_date}"
        filename += ".xlsx"
        
        # Set up the response with appropriate headers
        output.seek(0)
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response