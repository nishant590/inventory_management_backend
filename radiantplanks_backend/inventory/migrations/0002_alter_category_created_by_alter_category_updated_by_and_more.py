# Generated by Django 5.1.2 on 2024-10-28 05:38

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('inventory', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='category',
            name='created_by',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='category_created', to='authentication.newuser'),
        ),
        migrations.AlterField(
            model_name='category',
            name='updated_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='category_updated', to='authentication.newuser'),
        ),
        migrations.AlterField(
            model_name='product',
            name='created_by',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='products_created', to='authentication.newuser'),
        ),
        migrations.AlterField(
            model_name='product',
            name='updated_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='products_updated', to='authentication.newuser'),
        ),
    ]
