# Generated by Django 2.1.15 on 2020-12-05 01:30

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('parts', '0012_auto_20200119_2149'),
        ('notifications', '0020_auto_20200530_0008'),
    ]

    operations = [
        migrations.CreateModel(
            name='PartCategoryGroup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Enter a name for this group of part categories', max_length=255)),
                ('part_categories', models.ManyToManyField(help_text='Select which Part Categories should be included in this notification group.', to='parts.PartCategory')),
            ],
        ),
        migrations.CreateModel(
            name='PartNotice',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notification_type', models.CharField(choices=[('low_inventory', "Notify when inventory for a part falls below it's Low Inventory threshold")], default='low_inventory', max_length=128, verbose_name='Notification Type')),
                ('part_categories', models.ForeignKey(blank=True, help_text='Select which group of parts this notification should be limited to. Leave blank to include all parts', null=True, on_delete=django.db.models.deletion.PROTECT, to='notifications.PartCategoryGroup', verbose_name='Part Group filter')),
                ('recipients', models.ForeignKey(help_text='Choose the group of recipients who should receive these notifications', on_delete=django.db.models.deletion.PROTECT, to='notifications.RecipientGroup', verbose_name='Recipients')),
            ],
            options={
                'verbose_name': 'Part Notice',
            },
        ),
    ]
