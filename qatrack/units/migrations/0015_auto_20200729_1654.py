# Generated by Django 2.1.15 on 2020-07-29 20:54

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('units', '0014_auto_20191128_2343'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='modality',
            options={'verbose_name': 'modality', 'verbose_name_plural': 'modalities'},
        ),
        migrations.AlterModelOptions(
            name='site',
            options={'ordering': ('name',), 'verbose_name': 'site', 'verbose_name_plural': 'sites'},
        ),
        migrations.AlterModelOptions(
            name='unit',
            options={'ordering': ['name'], 'verbose_name': 'unit', 'verbose_name_plural': 'units'},
        ),
        migrations.AlterModelOptions(
            name='unitavailabletime',
            options={'default_permissions': ('change',), 'get_latest_by': 'date_changed', 'ordering': ['-date_changed'], 'verbose_name': 'unit available time', 'verbose_name_plural': 'unit available times'},
        ),
        migrations.AlterModelOptions(
            name='unitavailabletimeedit',
            options={'default_permissions': (), 'get_latest_by': 'date', 'ordering': ['-date'], 'verbose_name': 'unit available time edit', 'verbose_name_plural': 'unit available time edits'},
        ),
        migrations.AlterModelOptions(
            name='unitclass',
            options={'ordering': ('name',), 'verbose_name': 'unit class', 'verbose_name_plural': 'unit classes'},
        ),
        migrations.AlterModelOptions(
            name='unittype',
            options={'ordering': ('vendor__name', 'name'), 'verbose_name': 'unit type', 'verbose_name_plural': 'unit types'},
        ),
        migrations.AlterModelOptions(
            name='vendor',
            options={'ordering': ('name',), 'verbose_name': 'Vendor', 'verbose_name_plural': 'Vendor'},
        ),
        migrations.AddField(
            model_name='unittype',
            name='collapse',
            field=models.BooleanField(default=False, help_text='Collapse this unit type in the user interface by default', verbose_name='Collapse'),
        ),
        migrations.AlterField(
            model_name='site',
            name='name',
            field=models.CharField(help_text='Name of this site', max_length=64, unique=True, verbose_name='name'),
        ),
        migrations.AlterField(
            model_name='site',
            name='slug',
            field=models.SlugField(help_text='Unique identifier made of lowercase characters and underscores for this site', unique=True, verbose_name='slug'),
        ),
        migrations.AlterField(
            model_name='unitclass',
            name='name',
            field=models.CharField(help_text='Name of this unit class', max_length=64, unique=True, verbose_name='name'),
        ),
        migrations.AlterField(
            model_name='unittype',
            name='model',
            field=models.CharField(blank=True, help_text='Optional model name for this group', max_length=50, null=True, verbose_name='model'),
        ),
        migrations.AlterField(
            model_name='unittype',
            name='name',
            field=models.CharField(help_text='Name for this unit type', max_length=50, verbose_name='name'),
        ),
        migrations.AlterField(
            model_name='unittype',
            name='unit_class',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='units.UnitClass', verbose_name='unit class'),
        ),
        migrations.AlterField(
            model_name='unittype',
            name='vendor',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='units.Vendor', verbose_name='vendor'),
        ),
        migrations.AlterField(
            model_name='vendor',
            name='name',
            field=models.CharField(help_text='Name of this vendor', max_length=64, unique=True, verbose_name='name'),
        ),
        migrations.AlterField(
            model_name='vendor',
            name='notes',
            field=models.TextField(blank=True, help_text='Additional notes about this vendor', max_length=255, null=True, verbose_name='notes'),
        ),
    ]
