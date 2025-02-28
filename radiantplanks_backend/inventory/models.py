from django.db import models
from authentication.models import NewUser
from customers.models import Customer, Vendor
from accounts.models import Transaction
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
    barcode = models.CharField(max_length=100, null=True, blank=True)
    category_id = models.ForeignKey(Category, related_name='products', on_delete=models.CASCADE, null=True, blank=True)
    # subcategory = models.CharField(max_length=255, null=True, blank=True)  # Optional subcategory
    purchase_description = models.TextField(null=True, blank=True)
    # sell_description = models.TextField(null=True, blank=True)

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
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, null=True, blank=True)
    # selling_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
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
    # income_account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='income_mappings')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Mapping for {self.product.product_name}"


class Invoice(models.Model):
    PAYMENT_STATUS_CHOICES = (
        ("unpaid", "Unpaid"),
        ("partially_paid", "Partially Paid"),
        ("paid", "Paid"),
    )
    # invoice_code = models.IntegerField(default=0)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    customer_email = models.CharField(max_length=100, null=True)
    customer_email_cc = models.CharField(max_length=255, null=True, blank=True)  # For CC/BCC
    customer_email_bcc = models.CharField(max_length=255, null=True, blank=True)
    billing_address_street_1 = models.CharField(max_length=255, null=True, blank=True)  # Billing address
    billing_address_street_2 = models.CharField(max_length=255, null=True, blank=True)  # Billing address
    billing_address_city = models.CharField(max_length=100, null=True, blank=True)  # Billing address
    billing_address_state = models.CharField(max_length=100, null=True, blank=True)  # Billing address
    billing_address_postal_code = models.CharField(max_length=20, null=True, blank=True)  # Billing address
    billing_address_country = models.CharField(max_length=100, null=True, blank=True)  # Billing address
    shipping_address_street_1 = models.CharField(max_length=255, null=True, blank=True)  # shipping address
    shipping_address_street_2 = models.CharField(max_length=255, null=True, blank=True)  # shipping address
    shipping_address_city = models.CharField(max_length=100, null=True, blank=True)  # shipping address
    shipping_address_state = models.CharField(max_length=100, null=True, blank=True)  # shipping address
    shipping_address_postal_code = models.CharField(max_length=20, null=True, blank=True)  # shipping address
    shipping_address_country = models.CharField(max_length=100, null=True, blank=True)  # shipping address
    tags = models.CharField(max_length=255, null=True, blank=True)  # Tags field
    terms = models.TextField(null=True, blank=True)  # Terms field
    bill_date = models.DateTimeField(default=timezone.now)  # Redundant, could be removed
    due_date = models.DateTimeField(default=timezone.now)  # Due date
    payment_date = models.DateField(null=True, blank=True)  # Payment date
    # invoice_number = models.CharField(max_length=50, unique=True)  # Invoice num
    message_on_invoice = models.TextField(null=True, blank=True)  # Message on invoice
    message_on_statement = models.TextField(null=True, blank=True)  # Message on statement
    sum_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    is_taxed = models.BooleanField(default=False)
    tax_percentage = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    unpaid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS_CHOICES, default="unpaid"
    )
    attachments = models.CharField(max_length=255, null=True, blank=True)
    created_by = models.ForeignKey(NewUser, on_delete=models.CASCADE, related_name="invoice_created_by")
    created_date = models.DateTimeField(default=timezone.now)
    updated_by = models.ForeignKey(NewUser, on_delete=models.CASCADE, related_name="invoice_updated_by", null=True)
    updated_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Invoice {self.id} - Customer {self.customer} - Total {self.total_amount}"


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
    PAYMENT_STATUS_CHOICES = (
        ("unpaid", "Unpaid"),
        ("partially paid", "Partially Paid"),
        ("paid", "Paid"),
    )
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    mailing_address_street_1 = models.CharField(max_length=255, null=True, blank=True)  # Billing address
    mailing_address_street_2 = models.CharField(max_length=255, null=True, blank=True)  # Billing address
    mailing_address_city = models.CharField(max_length=100, null=True, blank=True)  # Billing address
    mailing_address_state = models.CharField(max_length=100, null=True, blank=True)  # Billing address
    mailing_address_postal_code = models.CharField(max_length=20, null=True, blank=True)  # Billing address
    mailing_address_country = models.CharField(max_length=100, null=True, blank=True)  # Billing address
    bill_number = models.CharField(max_length=255, null=True, blank=True)
    tags = models.CharField(max_length=255, null=True, blank=True)
    terms = models.TextField(null=True, blank=True)
    bill_date = models.DateTimeField(default=timezone.now)
    due_date = models.DateTimeField(default=timezone.now)
    payment_date = models.DateField(null=True, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    unpaid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS_CHOICES, default="unpaid"
    )
    memo = models.TextField(null=True, blank=True)
    attachments = models.CharField(max_length=255, null=True, blank=True)
    created_by = models.ForeignKey(NewUser, on_delete=models.CASCADE, related_name="bill_created_by", null=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)


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
        return f"Item {self.id} - bill {self.bill} - Product {self.product_id}"
    

class InvoiceTransactionMapping(models.Model):
    invoice_id = models.CharField(max_length=255)  # Unique Invoice ID
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Mapping for Invoice {self.invoice_id}"
    

class BillTransactionMapping(models.Model):
    bill_id = models.CharField(max_length=255)  # Unique bill ID
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Mapping for Invoice {self.bill_id}"
    

class LostProduct(models.Model):
    LOSS_REASON_CHOICES = [
        ('damaged', 'Damaged'),
        ('other', 'Other'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='lost_products')
    quantity_lost = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, help_text="Cost per unit at the time of loss.")
    total_loss = models.DecimalField(max_digits=10, decimal_places=2, editable=False, help_text="Calculated as quantity_lost * unit_cost.")
    reason = models.CharField(max_length=50, choices=LOSS_REASON_CHOICES, default='damaged')
    loss_date = models.DateField(auto_now_add=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True, related_name='lost_products', help_text="Optional: Link to an invoice if the loss is related to a specific transaction.")
    notes = models.TextField(null=True, blank=True, help_text="Additional details about the loss.")
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='lost_product')
    created_by = models.ForeignKey(NewUser, on_delete=models.CASCADE, related_name='lost_products_created')
    created_date = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(NewUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='lost_products_updated')
    updated_date = models.DateTimeField(auto_now=True)


    def __str__(self):
        return f"Lost Product: {self.product.product_name} - Quantity: {self.quantity_lost} - Loss: {self.total_loss}"