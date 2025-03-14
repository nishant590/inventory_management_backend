# Generated by Django 5.1.2 on 2025-02-26 06:03

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0014_ownerpaymentdetails_transaction_type'),
        ('inventory', '0032_remove_invoice_invoice_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='lostproduct',
            name='transaction_map',
            field=models.ForeignKey(default=98, on_delete=django.db.models.deletion.CASCADE, related_name='lost_product', to='accounts.transaction'),
            preserve_default=False,
        ),
    ]
