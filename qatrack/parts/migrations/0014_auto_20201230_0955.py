# Generated by Django 2.1.15 on 2020-12-30 14:55

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('parts', '0013_auto_20201229_1302'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='partsuppliercollection',
            unique_together={('part', 'supplier', 'part_number')},
        ),
    ]