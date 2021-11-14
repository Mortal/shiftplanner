# Generated by Django 3.2.7 on 2021-11-14 12:36

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shifts", "0002_shift_date_index"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkerShiftComment",
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
                ("comment", models.TextField()),
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
    ]
