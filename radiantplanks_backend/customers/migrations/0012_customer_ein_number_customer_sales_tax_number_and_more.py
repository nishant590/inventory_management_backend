# Generated by Django 5.1.2 on 2025-03-03 08:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0011_customer_tax_exempt'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='ein_number',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='customer',
            name='sales_tax_number',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='vendor',
            name='ein_number',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='vendor',
            name='sales_tax_number',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='vendoraddress',
            name='city',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='vendoraddress',
            name='country',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='vendoraddress',
            name='state',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='vendoraddress',
            name='street_add_2',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
