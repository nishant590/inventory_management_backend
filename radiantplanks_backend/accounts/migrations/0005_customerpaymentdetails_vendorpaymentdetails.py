# Generated by Django 5.1.2 on 2024-12-06 09:54

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_transaction_is_active_transactionline_is_active_and_more'),
        ('customers', '0008_customer_bcc_email_customer_cc_email_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomerPaymentDetails',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('payment_method', models.CharField(max_length=50)),
                ('transaction_reference_id', models.CharField(blank=True, max_length=100, null=True)),
                ('bank_name', models.CharField(blank=True, max_length=100, null=True)),
                ('cheque_number', models.CharField(blank=True, max_length=50, null=True)),
                ('payment_amount', models.DecimalField(decimal_places=2, max_digits=15)),
                ('payment_date', models.DateField()),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='customer_payment_details', to='customers.customer')),
                ('transaction', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='payment_details', to='accounts.transaction')),
            ],
        ),
        migrations.CreateModel(
            name='VendorPaymentDetails',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('payment_method', models.CharField(max_length=50)),
                ('transaction_reference_id', models.CharField(blank=True, max_length=100, null=True)),
                ('bank_name', models.CharField(blank=True, max_length=100, null=True)),
                ('cheque_number', models.CharField(blank=True, max_length=50, null=True)),
                ('payment_amount', models.DecimalField(decimal_places=2, max_digits=15)),
                ('payment_date', models.DateField()),
                ('transaction', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='vendor_payment_details', to='accounts.transaction')),
                ('vendor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='vendor_payment_details', to='customers.vendor')),
            ],
        ),
    ]