# Generated by Django 5.1.2 on 2024-12-04 06:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0005_rename_street_vendoraddress_street_add_1_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='vendor',
            name='mobile_number',
            field=models.CharField(default='', max_length=15),
            preserve_default=False,
        ),
    ]