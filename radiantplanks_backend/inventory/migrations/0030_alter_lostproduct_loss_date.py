# Generated by Django 5.1.2 on 2025-02-24 12:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0029_lostproduct'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lostproduct',
            name='loss_date',
            field=models.DateField(auto_now_add=True),
        ),
    ]
