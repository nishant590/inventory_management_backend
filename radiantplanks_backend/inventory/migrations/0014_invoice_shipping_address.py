# Generated by Django 5.1.2 on 2024-11-28 04:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0013_invoice_tax_amount'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='shipping_address',
            field=models.TextField(blank=True, null=True),
        ),
    ]
