# Generated by Django 5.1.2 on 2024-12-06 09:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0020_alter_bill_bill_number'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='bill',
            name='is_paid',
        ),
        migrations.RemoveField(
            model_name='invoice',
            name='is_paid',
        ),
        migrations.AddField(
            model_name='bill',
            name='paid_amount',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
        ),
        migrations.AddField(
            model_name='bill',
            name='payment_status',
            field=models.CharField(choices=[('unpaid', 'Unpaid'), ('partially paid', 'Partially Paid'), ('paid', 'Paid')], default='unpaid', max_length=20),
        ),
        migrations.AddField(
            model_name='bill',
            name='unpaid_amount',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
        ),
        migrations.AddField(
            model_name='invoice',
            name='paid_amount',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
        ),
        migrations.AddField(
            model_name='invoice',
            name='payment_status',
            field=models.CharField(choices=[('unpaid', 'Unpaid'), ('partially paid', 'Partially Paid'), ('paid', 'Paid')], default='unpaid', max_length=20),
        ),
        migrations.AddField(
            model_name='invoice',
            name='unpaid_amount',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
        ),
        migrations.AlterField(
            model_name='bill',
            name='total_amount',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
        ),
    ]
