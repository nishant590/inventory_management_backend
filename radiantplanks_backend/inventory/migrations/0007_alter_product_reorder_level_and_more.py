# Generated by Django 5.1.2 on 2024-11-23 06:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0006_remove_product_price_invoice_bill_date_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='reorder_level',
            field=models.PositiveIntegerField(blank=True, default=0, null=True),
        ),
        migrations.AlterField(
            model_name='product',
            name='stock_quantity',
            field=models.PositiveIntegerField(blank=True, default=0, null=True),
        ),
    ]