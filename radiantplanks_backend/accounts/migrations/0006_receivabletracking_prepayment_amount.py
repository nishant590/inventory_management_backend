# Generated by Django 5.1.2 on 2024-12-06 10:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_customerpaymentdetails_vendorpaymentdetails'),
    ]

    operations = [
        migrations.AddField(
            model_name='receivabletracking',
            name='prepayment_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=15),
        ),
    ]
