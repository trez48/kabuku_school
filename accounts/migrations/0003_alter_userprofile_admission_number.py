# Migration to make admission_number null=True, unique=True
# Rewritten to use standard Django operations (MySQL/MariaDB compatible)
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_userprofile_must_change_password_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='admission_number',
            field=models.CharField(blank=True, null=True, max_length=50, unique=True),
        ),
    ]
