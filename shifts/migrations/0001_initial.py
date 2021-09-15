# Generated by Django 3.2.7 on 2021-09-15 11:51

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import shifts.django_datetime_utc


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Shift",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("date", models.DateField()),
                ("order", models.PositiveSmallIntegerField()),
                ("slug", models.SlugField(max_length=150)),
                ("name", models.CharField(max_length=150)),
                ("settings", models.TextField(default="{}")),
            ],
        ),
        migrations.CreateModel(
            name="Worker",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=150)),
                (
                    "phone",
                    models.CharField(
                        blank=True, db_index=True, max_length=40, null=True
                    ),
                ),
                (
                    "login_secret",
                    models.CharField(blank=True, max_length=150, null=True),
                ),
                (
                    "cookie_secret",
                    models.CharField(blank=True, max_length=150, null=True),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Workplace",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("slug", models.SlugField(max_length=150)),
                ("name", models.CharField(max_length=150)),
                ("settings", models.TextField(default="{}")),
            ],
        ),
        migrations.CreateModel(
            name="WorkerShift",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("order", models.PositiveSmallIntegerField()),
                (
                    "shift",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="shifts.shift"
                    ),
                ),
                (
                    "worker",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="shifts.worker"
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="shift",
            name="workplace",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="shifts.workplace"
            ),
        ),
        migrations.CreateModel(
            name="Changelog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("time", shifts.django_datetime_utc.DateTimeUTCField(db_index=True)),
                ("kind", models.CharField(db_index=True, max_length=150)),
                ("data", models.TextField(blank=True)),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "worker",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="shifts.worker",
                    ),
                ),
            ],
        ),
    ]
