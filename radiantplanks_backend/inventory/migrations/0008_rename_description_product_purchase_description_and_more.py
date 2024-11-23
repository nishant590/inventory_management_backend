# Generated by Django 5.1.2 on 2024-11-23 08:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0007_alter_product_reorder_level_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='product',
            old_name='description',
            new_name='purchase_description',
        ),
        migrations.AddField(
            model_name='product',
            name='no_of_tiles',
            field=models.PositiveIntegerField(blank=True, default=0, null=True),
        ),
        migrations.AddField(
            model_name='product',
            name='sell_description',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='product',
            name='specifications',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
