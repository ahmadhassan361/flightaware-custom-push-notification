# Generated by Django 3.2.18 on 2023-06-20 11:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='StoreTrack',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('flight_id', models.CharField(blank=True, max_length=244, null=True)),
                ('token', models.CharField(blank=True, max_length=244, null=True)),
            ],
        ),
    ]
