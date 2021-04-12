# Generated by Django 2.1.11 on 2020-03-03 01:14

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('qa', '0051_wraparound_test'),
    ]

    operations = [
        migrations.AlterField(
            model_name='testinstance',
            name='reference',
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.PROTECT, to='qa.Reference'),
        ),
        migrations.AlterField(
            model_name='testinstance',
            name='tolerance',
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.PROTECT, to='qa.Tolerance'),
        ),
        migrations.AlterField(
            model_name='unittestinfo',
            name='reference',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='qa.Reference', verbose_name='Current Reference'),
        ),
        migrations.AlterField(
            model_name='unittestinfo',
            name='tolerance',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='qa.Tolerance'),
        ),
    ]
