from django.db import models
from customers.models import Vendor
from django.utils import timezone
from django.utils.timezone import now
from authentication.models import NewUser
from accounts.models import Account

class Expense(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    expense_number = models.CharField(max_length=255, unique=True, null=True, blank=True)
    expense_account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='expense_account')
    tags = models.CharField(max_length=255, null=True, blank=True)
    payment_date = models.DateTimeField(default=timezone.now)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_paid = models.BooleanField(default=False)
    memo = models.TextField(null=True, blank=True)
    attachments = models.CharField(max_length=255, null=True, blank=True)
    created_by = models.ForeignKey(NewUser, on_delete=models.CASCADE, related_name="expense_created_by", null=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)


class ExpenseItems(models.Model):
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name="expenseitems")
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="expenseitem_account")
    description = models.CharField(max_length=100, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_by = models.ForeignKey(NewUser, on_delete=models.CASCADE, related_name="expenseitem_created_by")
    created_date = models.DateTimeField(default=timezone.now)
    updated_by = models.ForeignKey(NewUser, on_delete=models.CASCADE, related_name="expenseitem_updated_by", null=True)
    updated_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def line_total(self):
        return self.price

    def __str__(self):
        return f"Item {self.id} - Invoice {self.expense} - Product {self.account}"