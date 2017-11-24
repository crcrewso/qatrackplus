# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2017-10-27 15:51
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('issue_tracker', '0013_auto_20170531_1516'),
    ]

    operations = [
        migrations.AlterField(
            model_name='issue',
            name='issue_tags',
            field=models.ManyToManyField(blank=True, help_text='If desired, add multiple tags to this issue', to='issue_tracker.IssueTag'),
        ),
    ]