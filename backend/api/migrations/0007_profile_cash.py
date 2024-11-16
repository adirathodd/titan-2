# Generated by Django 5.1.2 on 2024-11-13 06:48

import django.core.validators
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0006_remove_profile_cash_stock_current_price_transaction_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='cash',
            field=models.DecimalField(decimal_places=2, default=Decimal('10000.00'), help_text='Amount of money available to the user.', max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal('0.00'))]),
        ),
    ]