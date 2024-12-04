# Generated by Django 5.1.2 on 2024-12-04 05:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0003_auditlog'),
    ]

    operations = [
        migrations.RenameField(
            model_name='auditlog',
            old_name='last_login_city',
            new_name='activity_city',
        ),
        migrations.RenameField(
            model_name='auditlog',
            old_name='last_login_country',
            new_name='activity_country',
        ),
        migrations.AddField(
            model_name='auditlog',
            name='activity_ip',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
