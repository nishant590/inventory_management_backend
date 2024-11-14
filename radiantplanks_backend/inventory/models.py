from django.db import models
from authentication.models import NewUser
from customers.models import Customer
from django.utils import timezone

class Category(models.Model):
    name = models.CharField(max_length=255, unique=True)
    type = models.CharField(max_length=10, choices=[('expense', 'Expense'), ('income', 'Income')])
    created_by = models.ForeignKey(NewUser, related_name='category_created', on_delete=models.CASCADE)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(NewUser, related_name='category_updated', on_delete=models.CASCADE, null=True, blank=True)
    updated_date = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(Category, related_name='products', on_delete=models.CASCADE)
    product_name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.PositiveIntegerField()
    created_by = models.ForeignKey(NewUser, related_name='products_created', on_delete=models.CASCADE)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(NewUser, related_name='products_updated', on_delete=models.CASCADE, null=True, blank=True)
    updated_date = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.product_name


class Invoice(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    date = models.DateTimeField(default=timezone.now)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_by = models.ForeignKey(NewUser, on_delete=models.CASCADE, related_name="invoice_created_by")
    created_date = models.DateTimeField(default=timezone.now)
    updated_by = models.ForeignKey(NewUser, on_delete=models.CASCADE, related_name="invoice_updated_by", null=True)
    updated_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Invoice {self.id} - Customer {self.customer_id} - Total {self.total_amount}"

class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    created_by = models.ForeignKey(NewUser, on_delete=models.CASCADE, related_name="invoiceitem_created_by")
    created_date = models.DateTimeField(default=timezone.now)
    updated_by = models.ForeignKey(NewUser, on_delete=models.CASCADE, related_name="invoiceitem_updated_by", null=True)
    updated_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def line_total(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"Item {self.id} - Invoice {self.invoice_id} - Product {self.product_id}"