#!/usr/bin/env python

import argparse
import datetime
import json
import os

parser = argparse.ArgumentParser()
parser.add_argument("action")


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "shiftplanner.settings")
    with open("env.txt") as fp:
        for line in fp:
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()
    import django

    django.setup()

    args = parser.parse_args()
    if args.action == "create":
        create_dummy_data()
    elif args.action == "clear":
        clear_all_data()


def clear_all_data():
    from shifts import models

    (workplace,) = models.Workplace.objects.all()
    if workplace.name != "ACME & Sons":
        raise SystemExit("Refuse to clear data for %r" % (workplace.name,))
    models.WorkerShift.objects.all().delete()
    models.Shift.objects.all().delete()
    models.Changelog.objects.all().delete()
    models.Worker.objects.all().delete()
    models.Workplace.objects.all().delete()


def create_dummy_data():
    from shifts import models

    workplace_settings: models.WorkplaceSettings = {
        "weekday_defaults": {
            "monday": {
                "registration_deadline": "-3dT18:00",
                "shifts": ["DV", "AV", "NV"],
            },
            "tuesday": {
                "registration_deadline": "-4dT18:00",
                "shifts": ["DV", "AV", "NV"],
            },
            "wednesday": {
                "registration_deadline": "-5dT18:00",
                "shifts": ["DV", "AV", "NV"],
            },
        },
    }
    if models.Workplace.objects.exists():
        (workplace,) = models.Workplace.objects.all()
    else:
        workplace = models.Workplace(
            slug="acme", name="ACME & Sons", settings=json.dumps(workplace_settings)
        )
    first_names = [
        "Alice",
        "Bob",
        "Carla",
        "David",
        "Emma",
        "Florence",
        "Giuseppe",
        "Henry",
        "Ivan",
        "Julia",
    ]
    last_names = list("BDGHKMNPRSTV")
    worker_names = [f"{first} {last}" for first in first_names for last in last_names]
    phones = [
        "2%s%04d" % (str(2 ** (1 / (2 + i)))[-3:], i) for i in range(len(worker_names))
    ]
    login_secrets = [
        "%016X" % int(2 ** 64 / 2 ** (1 / (2 + i))) for i in range(len(worker_names))
    ]
    workers = [
        models.Worker(
            name=name,
            phone=phone,
            login_secret=secret,
        )
        for name, phone, secret in zip(worker_names, phones, login_secrets)
    ]
    first_day = datetime.date(2022, 1, 1)
    shifts = [
        s
        for day in range(7)
        for s in models.day_shifts_for_settings(
            first_day + datetime.timedelta(day), workplace_settings
        )
    ]
    assert shifts
    if not workplace.id:
        workplace.save()
    for w in workers:
        w.save()
    for i, s in enumerate(shifts):
        s.workplace = workplace
        s.save()
        for j in range(3):
            worker = workers[((3 * i + j) * 7919) % len(workers)]
            models.WorkerShift.objects.create(worker=worker, shift=s, order=i + 1)


if __name__ == "__main__":
    main()
