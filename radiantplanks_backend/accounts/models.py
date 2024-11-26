from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from authentication.models import NewUser
from datetime import datetime, timedelta
from django.http import JsonResponse
from django.conf import settings
# Create your models here.

class Account(models.Model):
    ACCOUNT_TYPES = [
        # Expanded Account Types
        # Assets
        ('cash', 'Cash'),
        ('bank', 'Bank'),
        ('accounts_receivable', 'Accounts Receivable'),
        ('inventory', 'Inventory'),
        ('fixed_assets', 'Fixed Assets'),
        ('other_current_assets', 'Other Current Assets'),
        
        # Liabilities
        ('accounts_payable', 'Accounts Payable'),
        ('credit_card', 'Credit Card'),
        ('current_liabilities', 'Current Liabilities'),
        ('long_term_liabilities', 'Long Term Liabilities'),
        
        # Equity
        ('owner_equity', 'Owner Equity'),
        ('retained_earnings', 'Retained Earnings'),
        
        # Income
        ('sales_income', 'Sales Income'),
        ('service_income', 'Service Income'),
        ('other_income', 'Other Income'),
        
        # Expenses
        ('cost_of_goods_sold', 'Cost of Goods Sold'),
        ('operating_expenses', 'Operating Expenses'),
        ('payroll_expenses', 'Payroll Expenses'),
        ('marketing_expenses', 'Marketing Expenses'),
        ('administrative_expenses', 'Administrative Expenses'),
        ('other_expenses', 'Other Expenses'),
    ]

    name = models.CharField(max_length=100)
    account_type = models.CharField(max_length=100, choices=ACCOUNT_TYPES)
    code = models.CharField(max_length=20, unique=True, null=True, blank=True)  # Account code for easy reference
    description = models.TextField(blank=True)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0.00'))])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.code} - {self.name}"

    class Meta:
        ordering = ['code']
    
    @classmethod
    def create_default_accounts(cls):
        """
        Create default system accounts if they don't exist
        """
        default_accounts = [
            # Asset Accounts
            {'name': 'Cash', 'account_type': 'cash', 'code': 'CASH-001'},
            {'name': 'Main Bank Account', 'account_type': 'bank', 'code': 'BANK-001'},
            {'name': 'Accounts Receivable', 'account_type': 'accounts_receivable', 'code': 'AR-001'},
            {'name': 'Inventory', 'account_type': 'inventory', 'code': 'INV-001'},
            
            # Liability Accounts
            {'name': 'Accounts Payable', 'account_type': 'accounts_payable', 'code': 'AP-001'},
            
            # Income Accounts
            {'name': 'Sales Revenue', 'account_type': 'sales_income', 'code': 'INC-001'},
            
            # Expense Accounts
            {'name': 'Cost of Goods Sold', 'account_type': 'cost_of_goods_sold', 'code': 'COGS-001'},
        ]

        for account_data in default_accounts:
            cls.objects.get_or_create(
                code=account_data['code'], 
                defaults=account_data
            )

    
class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('expense', 'Expense'),
        ('income', 'Income'),
        ('transfer', 'Transfer'),
        ('journal', 'Journal Entry'),
    ]

    reference_number = models.CharField(max_length=50, unique=True)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    date = models.DateField()
    description = models.TextField()
    is_reconciled = models.BooleanField(default=False)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    attachment = models.CharField(max_length=100, null=True, blank=True)
    created_by = models.ForeignKey(NewUser, on_delete=models.PROTECT, related_name='created_transactions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date', '-created_at']

class TransactionLine(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='lines')
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    description = models.CharField(max_length=255, blank=True)
    debit_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0.00'))])
    credit_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0.00'))])
    
    class Meta:
        ordering = ['id']

