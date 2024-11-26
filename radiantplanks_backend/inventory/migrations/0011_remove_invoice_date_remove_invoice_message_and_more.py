# Generated by Django 5.1.2 on 2024-11-26 06:38

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_alter_account_account_type'),
        ('authentication', '0002_newuser_last_login_city_newuser_last_login_country'),
        ('inventory', '0010_rename_category_product_category_id'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='invoice',
            name='date',
        ),
        migrations.RemoveField(
            model_name='invoice',
            name='message',
        ),
        migrations.AddField(
            model_name='invoice',
            name='billing_address',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='invoice',
            name='customer_email',
            field=models.CharField(max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='invoice',
            name='customer_email_bcc',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='invoice',
            name='customer_email_cc',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='invoice',
            name='message_on_invoice',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='invoice',
            name='message_on_statement',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='invoice',
            name='tags',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='invoice',
            name='terms',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='invoiceitem',
            name='amount',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
        ),
        migrations.AlterField(
            model_name='invoiceitem',
            name='unit_price',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
        ),
        migrations.AlterField(
            model_name='product',
            name='as_on_date',
            field=models.DateField(blank=True, default=django.utils.timezone.now, null=True),
        ),
        migrations.CreateModel(
            name='ProductAccountMapping',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('income_account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='income_mappings', to='accounts.account')),
                ('inventory_account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='inventory_mappings', to='accounts.account')),
                ('product', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='account_mapping', to='inventory.product')),
            ],
        ),
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, unique=True)),
                ('created_date', models.DateTimeField(auto_now_add=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tags_created', to='authentication.newuser')),
            ],
        ),
    ]
