# Generated by Django 2.2.18 on 2021-03-23 17:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('units', '0018_auto_20210317_1538'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='modality',
            options={'verbose_name': 'treatment and imaging modality', 'verbose_name_plural': 'treatment and imaging modalities'},
        ),
        migrations.AlterField(
            model_name='modality',
            name='name',
            field=models.CharField(help_text='Descriptive name for this treatment or imaging modality.', max_length=255, unique=True, verbose_name='Name'),
        ),
    ]
