from django.db import models
from django.conf import settings
from authentication.models import NewUser


class Customer(models.Model):
    customer_id = models.AutoField(primary_key=True)
    first_name = models.CharField(max_length=50)
    middle_name = models.CharField(max_length=50, blank=True, null=True)
    last_name = models.CharField(max_length=50)
    display_name = models.CharField(max_length=100)
    company = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, null=True)
    mobile_number = models.CharField(max_length=15, null=True)
    # payments = models.CharField(max_length=20, choices=[('cash', 'Cash'), ('check', 'Check'),('credit card','Credit Card')], default="cash")
    # taxes = models.CharField(max_length=150)
    created_by = models.ForeignKey(NewUser, on_delete=models.SET_NULL, related_name='customer_created_by', null=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(NewUser, on_delete=models.SET_NULL, related_name='customer_updated_by', null=True)
    updated_date = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)


    def __str__(self):
        return self.display_name


class Address(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='addresses')
    address_type = models.CharField(max_length=30, choices=[('Billing', 'Billing'), ('Shipping', 'Shipping'),
                        ('Billing and Shipping','Billing and Shipping')])
    street_add_1 = models.CharField(max_length=255, null=True, blank=True)
    street_add_2 = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    state = models.CharField(max_length=100, null=True, blank=True)
    postal_code = models.CharField(max_length=20, null=True, blank=True)
    country = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f"{self.address_type.capitalize()} Address for {self.customer.display_name}"


class Vendor(models.Model):
    vendor_id = models.AutoField(primary_key=True)
    first_name = models.CharField(max_length=50)
    middle_name = models.CharField(max_length=50, blank=True, null=True)
    last_name = models.CharField(max_length=50)
    display_name = models.CharField(max_length=100)
    company = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15)
    created_by = models.ForeignKey(NewUser, on_delete=models.SET_NULL, related_name='vendor_created_by', null=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(NewUser, on_delete=models.SET_NULL, related_name='vendor_updated_by', null=True)
    updated_date = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.display_name


class VendorAddress(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='vendor_addresses')
    address_type = models.CharField(max_length=10, choices=[('Billing', 'Billing'), ('Shipping', 'Shipping'), 
                                                            ('Billing and Shipping', 'Billing and Shipping')])
    street_add_1 = models.CharField(max_length=255)
    street_add_2 = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.address_type.capitalize()} Address for {self.vendor.display_name}"

