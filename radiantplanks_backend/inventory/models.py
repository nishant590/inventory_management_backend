from django.db import models
from authentication.models import NewUser
from customers.models import Customer, Vendor
from django.utils import timezone
from django.utils.timezone import now
from accounts.models import Account



class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)  # Tag name
    created_by = models.ForeignKey(NewUser, on_delete=models.CASCADE, related_name="tags_created")
    created_date = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


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
    PRODUCT_TYPE_CHOICES = [
        ('product', 'Product'),
        ('service', 'Service'),
    ]

    product_type = models.CharField(max_length=10, choices=PRODUCT_TYPE_CHOICES, default='product')
    product_name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, unique=True, null=True, blank=True)
    barcode = models.CharField(max_length=100, unique=True, null=True, blank=True)
    category_id = models.ForeignKey(Category, related_name='products', on_delete=models.CASCADE, null=True, blank=True)
    # subcategory = models.CharField(max_length=255, null=True, blank=True)  # Optional subcategory
    purchase_description = models.TextField(null=True, blank=True)
    sell_description = models.TextField(null=True, blank=True)

    # Stock Details
    stock_quantity = models.PositiveIntegerField(default=0, null=True, blank=True)
    reorder_level = models.PositiveIntegerField(default=0, null=True, blank=True)
    batch_lot_number = models.CharField(max_length=100, null=True, blank=True)
    as_on_date = models.DateField(default=now, blank=True, null=True)
    tile_length = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # For tile dimensions
    tile_width = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    no_of_tiles = models.PositiveIntegerField(default=0, null=True, blank=True)
    tile_area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Pricing Information
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    # tax_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)  # e.g., 18.00 for 18%
    # discount = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)  # Discount percentage

    # Additional Product Information
    specifications = models.CharField(max_length=100, null=True, blank=True)  # Store additional details like dimensions, color, etc.
    tags = models.CharField(max_length=100, null=True, blank=True)  # Comma-separated tags
    images = models.CharField(max_length=150, null=True, blank=True)  # Store multiple image paths or URLs

    # Common Fields
    created_by = models.ForeignKey(NewUser, related_name='products_created', on_delete=models.CASCADE)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(NewUser, related_name='products_updated', on_delete=models.CASCADE, null=True, blank=True)
    updated_date = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.item_name
    

class ProductAccountMapping(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='account_mapping')
    inventory_account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='inventory_mappings')
    income_account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='income_mappings')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Mapping for {self.product.product_name}"


class Invoice(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    customer_email = models.CharField(max_length=100, null=True)
    customer_email_cc = models.CharField(max_length=255, null=True, blank=True)  # For CC/BCC
    customer_email_bcc = models.CharField(max_length=255, null=True, blank=True)
    billing_address = models.TextField(null=True, blank=True)  # Billing address
    shipping_address = models.TextField(null=True, blank=True)  # shipping address
    tags = models.CharField(max_length=255, null=True, blank=True)  # Tags field
    terms = models.TextField(null=True, blank=True)  # Terms field
    bill_date = models.DateTimeField(default=timezone.now)  # Redundant, could be removed
    due_date = models.DateTimeField(default=timezone.now)  # Due date
    # invoice_number = models.CharField(max_length=50, unique=True)  # Invoice num
    message_on_invoice = models.TextField(null=True, blank=True)  # Message on invoice
    message_on_statement = models.TextField(null=True, blank=True)  # Message on statement
    sum_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    is_taxed = models.BooleanField(default=False)
    tax_percentage = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    is_paid = models.BooleanField(default=False)
    attachments = models.CharField(max_length=255, null=True, blank=True)
    created_by = models.ForeignKey(NewUser, on_delete=models.CASCADE, related_name="invoice_created_by")
    created_date = models.DateTimeField(default=timezone.now)
    updated_by = models.ForeignKey(NewUser, on_delete=models.CASCADE, related_name="invoice_updated_by", null=True)
    updated_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Invoice {self.invoice_number} - Customer {self.customer} - Total {self.total_amount}"


# class Invoice(models.Model):
#     customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
#     customer_email = models.CharField(max_length=100, null=True)
#     date = models.DateTimeField(default=timezone.now)
#     sum_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
#     tax_percentage = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
#     total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
#     bill_date = models.DateTimeField(default=timezone.now )
#     due_date = models.DateTimeField(default=timezone.now )
#     message = models.CharField(max_length=100, null=True)
#     is_paid = models.BooleanField(default=False)
#     created_by = models.ForeignKey(NewUser, on_delete=models.CASCADE, related_name="invoice_created_by")
#     created_date = models.DateTimeField(default=timezone.now)
#     updated_by = models.ForeignKey(NewUser, on_delete=models.CASCADE, related_name="invoice_updated_by", null=True)
#     updated_date = models.DateTimeField(null=True, blank=True)
#     is_active = models.BooleanField(default=True)

#     def __str__(self):
#         return f"Invoice {self.id} - Customer {self.customer_id} - Total {self.total_amount}"


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    description = models.CharField(max_length=100, null=True)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    created_by = models.ForeignKey(NewUser, on_delete=models.CASCADE, related_name="invoiceitem_created_by")
    created_date = models.DateTimeField(default=timezone.now)
    updated_by = models.ForeignKey(NewUser, on_delete=models.CASCADE, related_name="invoiceitem_updated_by", null=True)
    updated_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def line_total(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"Item {self.id} - Invoice {self.invoice_id} - Product {self.product_id}"
    

class Estimate(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="estimate_customer")
    date = models.DateTimeField(default=timezone.now)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_by = models.ForeignKey(NewUser, on_delete=models.CASCADE, related_name="estimate_created_by")
    created_date = models.DateTimeField(default=timezone.now)
    updated_by = models.ForeignKey(NewUser, on_delete=models.CASCADE, related_name="estimate_updated_by", null=True)
    updated_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Estimate {self.id} - Customer {self.customer_id} - Total {self.total_amount}"


class EstimateItem(models.Model):
    estimate = models.ForeignKey(Estimate, on_delete=models.CASCADE, related_name="estimate_items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="estimate_product")
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    created_by = models.ForeignKey(NewUser, on_delete=models.CASCADE, related_name="estimateitem_created_by")
    created_date = models.DateTimeField(default=timezone.now)
    updated_by = models.ForeignKey(NewUser, on_delete=models.CASCADE, related_name="estimateitem_updated_by", null=True)
    updated_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def line_total(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"Item {self.id} - Estimate {self.invoice_id} - Product {self.product_id}"
    

class Bill(models.Model):
    # SOURCE_CHOICES = [('online', 'Online'), ('offline', 'Offline')]
    ACTION_CHOICES = [('paid', 'Paid'), ('pending', 'Pending')]

    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    source = models.CharField(max_length=50, null=True)
    bill_no = models.CharField(max_length=100, unique=True)
    bill_date = models.DateField()
    category = models.CharField(max_length=100, )
    due_date = models.DateField()
    bill_amount = models.DecimalField(max_digits=10, decimal_places=2)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class BillItems(models.Model):
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name="bills")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    description = models.CharField(max_length=100, null=True)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    created_by = models.ForeignKey(NewUser, on_delete=models.CASCADE, related_name="billitem_created_by")
    created_date = models.DateTimeField(default=timezone.now)
    updated_by = models.ForeignKey(NewUser, on_delete=models.CASCADE, related_name="billitem_updated_by", null=True)
    updated_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def line_total(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"Item {self.id} - Invoice {self.invoice_id} - Product {self.product_id}"