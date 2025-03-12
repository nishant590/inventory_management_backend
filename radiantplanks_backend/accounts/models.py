from django.db import models
from django.core.validators import MinValueValidator
from django.db.models import Case, When, Value, IntegerField
from decimal import Decimal
from authentication.models import NewUser
from datetime import datetime, timedelta
from django.http import JsonResponse
from customers.models import Customer, Vendor
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
        ('tax_payable', 'Tax Payable'),
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
            
            # Equity Accounts
            {'name': 'Owner Equity', 'account_type': 'owner_equity', 'code': 'OWN-001'},

            # Liability Accounts
            {'name': 'Accounts Payable', 'account_type': 'accounts_payable', 'code': 'AP-001'},
            {'name': 'Tax Payable', 'account_type': 'tax_payable', 'code': 'AP-002'},

            # Income Accounts
            {'name': 'Sales Revenue', 'account_type': 'sales_income', 'code': 'INC-001'},

            # Expense Accounts
            {'name': 'Cost of Goods Sold', 'account_type': 'cost_of_goods_sold', 'code': 'COGS-001'},
            {'name': 'Rent', 'account_type': 'operating_expenses', 'code': 'RE-001'},
            {'name': 'Utility', 'account_type': 'operating_expenses', 'code': 'UT-001'},
            {'name': 'Phone & Internet', 'account_type': 'operating_expenses', 'code': 'PH-001'},
            {'name': 'Advertising Material & Marketing', 'account_type': 'marketing_expenses', 'code': 'ADM-001'},
            {'name': 'Ocean Freight', 'account_type': 'operating_expenses', 'code': 'OF-001'},
            {'name': 'Annual Bond', 'account_type': 'other_expenses', 'code': 'AB-001'},
            {'name': 'Customs Clearing', 'account_type': 'operating_expenses', 'code': 'CC-001'},
            {'name': 'ISF Filing', 'account_type': 'administrative_expenses', 'code': 'ISF-001'},
            {'name': 'Delivery Order', 'account_type': 'operating_expenses', 'code': 'DO-001'},
            {'name': 'Drayage / Trucking', 'account_type': 'cost_of_goods_sold', 'code': 'DT-001'},
            {'name': 'Labor', 'account_type': 'payroll_expenses', 'code': 'LB-001'},
            {'name': 'Wire / Transfer Fee', 'account_type': 'administrative_expenses', 'code': 'WT-001'},
            {'name': 'Other Misc', 'account_type': 'other_expenses', 'code': 'MIS-001'},
        ]

        for account_data in default_accounts:
            cls.objects.get_or_create(
                code=account_data['code'],
                defaults={**account_data, 'balance': 0}
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
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(NewUser, on_delete=models.PROTECT, related_name='created_transactions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    
    class Meta:
        ordering = ['-date', '-created_at']


class CustomerPaymentDetails(models.Model):
    transaction = models.OneToOneField(Transaction, on_delete=models.CASCADE, related_name="payment_details")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="customer_payment_details")
    payment_method = models.CharField(max_length=50, null=True, blank=True)  # e.g., 'cash', 'bank_transfer', 'cheque'
    transaction_reference_id = models.CharField(max_length=100, null=True, blank=True)  # Bank transaction ID
    bank_name = models.CharField(max_length=100, null=True, blank=True)
    cheque_number = models.CharField(max_length=50, null=True, blank=True)
    payment_amount = models.DecimalField(max_digits=15, decimal_places=2)
    payment_date = models.DateField()

    def __str__(self):
        return f"Payment {self.id} - {self.payment_method}"


class VendorPaymentDetails(models.Model):
    transaction = models.OneToOneField(Transaction, on_delete=models.CASCADE, related_name="vendor_payment_details")
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="vendor_payment_details")
    payment_method = models.CharField(max_length=50, null=True, blank=True)  # e.g., 'cash', 'bank_transfer', 'cheque'
    transaction_reference_id = models.CharField(max_length=100, null=True, blank=True)  # Bank
    bank_name = models.CharField(max_length=100, null=True, blank=True)
    cheque_number = models.CharField(max_length=50, null=True, blank=True)
    payment_amount = models.DecimalField(max_digits=15, decimal_places=2)
    payment_date = models.DateField()
    
    def __str__(self):
        return f"Payment {self.id} - {self.payment_method}"
    

class OwnerPaymentDetails(models.Model):
    TRANSACTION_TYPES = [("money_added", "Money Added"),("money_removed", "Money Removed")]

    transaction = models.OneToOneField(Transaction, on_delete=models.CASCADE, related_name="owner_payment_details")
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES, default='money_added')
    description = models.CharField(max_length=255, blank=True, null=True)
    payment_method = models.CharField(max_length=50, null=True, blank=True)  # e.g., 'cash', 'bank_transfer', 'cheque'
    transaction_reference_id = models.CharField(max_length=100, null=True, blank=True)  # Bank
    payment_amount = models.DecimalField(max_digits=15, decimal_places=2)
    payment_date = models.DateField()
    money_flag = models.IntegerField(default=1)
    
    def save(self, *args, **kwargs):
        """Ensure money_flag is correctly set before saving."""
        self.money_flag = 1 if self.transaction_type == "money_added" else 0
        super().save(*args, **kwargs)

    @classmethod
    def update_old_records(cls):
        """Updates old records where money_flag is NULL."""
        cls.objects.filter(money_flag=1).update(
            money_flag=Case(
                When(transaction_type="money_added", then=Value(1)),
                When(transaction_type="money_removed", then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )

    def __str__(self):
        return f"Payment {self.id} - {self.payment_method}"


class TransactionLine(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='lines')
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    description = models.CharField(max_length=255, blank=True)
    debit_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0.00'))])
    credit_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0.00'))])
    invoice_id = models.IntegerField(null=True, blank=True, default=None)
    bill_id = models.IntegerField(null=True, blank=True, default=None)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['id']


class ReceivableTracking(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="receivables")
    receivable_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    advance_payment = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.customer.business_name} - {self.receivable_amount}"


class PayableTracking(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="payables")
    payable_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    advance_payment = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.vendor.business_name} - {self.payable_amount}"