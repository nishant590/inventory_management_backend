from django.db import models
from django.conf import settings
from authentication.models import NewUser


class Customer(models.Model):
    customer_id = models.AutoField(primary_key=True)
    first_name = models.CharField(max_length=50)
    middle_name = models.CharField(max_length=50, blank=True, null=True)
    last_name = models.CharField(max_length=50)
    business_name = models.CharField(max_length=120)
    company = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(unique=True)
    cc_email = models.EmailField(blank=True, null=True)
    bcc_email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=15, null=True)
    mobile_number = models.CharField(max_length=15, null=True)
    tax_exempt = models.BooleanField(default=False)
    sales_tax_number = models.CharField(max_length=100, blank=True, null=True)
    ein_number = models.CharField(max_length=100, blank=True, null=True)
    # payments = models.CharField(max_length=20, choices=[('cash', 'Cash'), ('check', 'Check'),('credit card','Credit Card')], default="cash")
    # taxes = models.CharField(max_length=150)
    created_by = models.ForeignKey(NewUser, on_delete=models.SET_NULL, related_name='customer_created_by', null=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(NewUser, on_delete=models.SET_NULL, related_name='customer_updated_by', null=True)
    updated_date = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)


    def __str__(self):
        return self.business_name


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
        return f"{self.address_type.capitalize()} Address for {self.customer.business_name}"


class Vendor(models.Model):
    vendor_id = models.AutoField(primary_key=True)
    first_name = models.CharField(max_length=50)
    middle_name = models.CharField(max_length=50, blank=True, null=True)
    last_name = models.CharField(max_length=50)
    business_name = models.CharField(max_length=120)
    company = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(unique=True)
    cc_email = models.EmailField(null=True, blank=True)
    bcc_email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=15)
    mobile_number = models.CharField(max_length=15)
    sales_tax_number = models.CharField(max_length=100, blank=True, null=True)
    ein_number = models.CharField(max_length=100, blank=True, null=True)
    created_by = models.ForeignKey(NewUser, on_delete=models.SET_NULL, related_name='vendor_created_by', null=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(NewUser, on_delete=models.SET_NULL, related_name='vendor_updated_by', null=True)
    updated_date = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    is_contractor = models.BooleanField(default=False)

    def __str__(self):
        return self.business_name


class VendorAddress(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='vendor_addresses')
    address_type = models.CharField(max_length=30, choices=[('Billing', 'Billing'), ('Shipping', 'Shipping'), 
                                                            ('Billing and Shipping', 'Billing and Shipping')])
    street_add_1 = models.CharField(max_length=255)
    street_add_2 = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    state = models.CharField(max_length=100, null=True, blank=True)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f"{self.address_type.capitalize()} Address for {self.vendor.business_name}"


class State(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'cities': [city.name for city in self.cities.all()]
        }

class City(models.Model):
    name = models.CharField(max_length=100)
    state = models.ForeignKey(State, related_name='cities', on_delete=models.CASCADE)

    class Meta:
        unique_together = ('name', 'state')
        verbose_name_plural = "Cities"

    def __str__(self):
        return f"{self.name}, {self.state.name}"
