# Generated by Django 5.1.2 on 2024-11-29 08:04

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts', '0003_receivabletracking'),
        ('authentication', '0002_newuser_last_login_city_newuser_last_login_country'),
        ('customers', '0004_remove_address_street_address_street_add_1_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Expense',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('expense_number', models.CharField(blank=True, max_length=255, null=True, unique=True)),
                ('tags', models.CharField(blank=True, max_length=255, null=True)),
                ('payment_date', models.DateTimeField(default=django.utils.timezone.now)),
                ('total_amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('is_paid', models.BooleanField(default=False)),
                ('memo', models.TextField(blank=True, null=True)),
                ('attachments', models.CharField(blank=True, max_length=255, null=True)),
                ('created_date', models.DateTimeField(auto_now_add=True)),
                ('updated_date', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=False)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='expense_created_by', to='authentication.newuser')),
                ('expense_account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='expense_account', to='accounts.account')),
                ('vendor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='customers.vendor')),
            ],
        ),
        migrations.CreateModel(
            name='ExpenseItems',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(max_length=100, null=True)),
                ('price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('created_date', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_date', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='expenseitem_account', to='accounts.account')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='expenseitem_created_by', to='authentication.newuser')),
                ('expense', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='expenseitems', to='expense.expense')),
                ('updated_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='expenseitem_updated_by', to='authentication.newuser')),
            ],
        ),
    ]