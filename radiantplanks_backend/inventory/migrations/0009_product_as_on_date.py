# Generated by Django 5.1.2 on 2024-11-23 10:13

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0008_rename_description_product_purchase_description_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='as_on_date',
            field=models.DateField(blank=True, default=django.utils.timezone.now),
        ),
    ]
