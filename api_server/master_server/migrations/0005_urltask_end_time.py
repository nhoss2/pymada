# Generated by Django 2.2.5 on 2020-01-02 06:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('master_server', '0004_auto_20191106_1703'),
    ]

    operations = [
        migrations.AddField(
            model_name='urltask',
            name='end_time',
            field=models.FloatField(default=0),
        ),
    ]
