# Generated by Django 2.1.15 on 2020-09-22 18:36

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0009_alter_user_last_name_max_length'),
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ActiveDirectoryGroupMap',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ad_group', models.CharField(help_text='Enter the name of the group from your Active Directory Server.', max_length=256, unique=True, verbose_name='Active Directory Group')),
                ('account_qualifier', models.BooleanField(default=False, help_text='Add this Active Directory Group to the set of Active Directory Groups of which a user must belong to at least one in order to log into QATrack+. (If there are no qualifying groups then all authenticated users may log into QATrack+.)', verbose_name='Account Qualifying Group')),
                ('groups', models.ManyToManyField(blank=True, help_text='Select the QATrack+ groups you want this user added to when they belong to the Active Directory Group', to='auth.Group', verbose_name='QATrack+ Groups')),
            ],
            options={
                'verbose_name': 'Active Directory Group to QATrack+ Group Map',
                'verbose_name_plural': 'Active Directory Group to QATrack+ Group Maps',
            },
        ),
        migrations.CreateModel(
            name='DefaultGroup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.Group')),
            ],
        ),
    ]
