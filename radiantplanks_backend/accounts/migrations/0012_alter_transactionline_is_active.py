# Generated by Django 5.1.2 on 2025-01-10 07:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0011_alter_transaction_is_active'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transactionline',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
    ]
