# Generated by Django 2.2.5 on 2020-01-03 08:59

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('master_server', '0006_auto_20200103_0745'),
    ]

    operations = [
        migrations.AddField(
            model_name='agent',
            name='assigned_task',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='master_server.UrlTask'),
        ),
    ]