# Generated by Django 5.1.2 on 2025-01-10 07:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0025_billtransactionmapping_invoicetransactionmapping'),
    ]

    operations = [
        migrations.AlterField(
            model_name='billtransactionmapping',
            name='bill_id',
            field=models.CharField(max_length=255),
        ),
        migrations.AlterField(
            model_name='invoicetransactionmapping',
            name='invoice_id',
            field=models.CharField(max_length=255),
        ),
    ]
