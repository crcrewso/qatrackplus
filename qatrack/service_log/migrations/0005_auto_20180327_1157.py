# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2018-03-27 15:57
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('service_log', '0004_auto_20180110_1257'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='returntoserviceqa',
            options={'permissions': (('view_returntoserviceqa', 'Can view return to service qa'), ('perform_returntoserviceqa', 'Can perform return to service qa'))},
        ),
    ]