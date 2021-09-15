#!/usr/bin/env python

import argparse
import datetime
import json
import os
import sys

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
    elif args.action == "export":
        export_all_data()
    elif args.action == "import":
        import_data()


def import_data():
    from shifts import models

    if models.Workplace.objects.exists():
        raise SystemExit("Please clear all data before importing")

    data = json.load(sys.stdin)
    workers = {
        k: models.Worker(
            name=w.get("name", k),
            phone=w.get("phone"),
            login_secret=w.get("login_secret"),
            cookie_secret=w.get("cookie_secret"),
        )
        for k, w in data["workers"].items()
    }
    workplaces = {}
    shifts = []
    worker_shifts = []
    for k, wp in data["workplaces"].items():
        wp_shifts = wp.pop("shifts", [])
        slug = wp.pop("slug", None)
        name = wp.pop("name", k)
        settings = json.dumps(wp)
        workplace = workplaces[k] = models.Workplace(
            slug=slug,
            name=name,
            settings=settings,
        )
        next_order = {}
        for s in wp_shifts:
            date = datetime.datetime.strptime(s.pop("date"), "%Y-%m-%d").date()
            order = next_order.get(date, 0) + 1
            next_order[date] = order
            shift_workers = s.pop("workers", [])
            shift = models.Shift(
                workplace=workplace,
                date=date,
                order=order,
                slug=s.pop("slug", None),
                name=s.pop("name", None),
                settings=json.dumps(s),
            )
            shifts.append(shift)
            for i, sw in enumerate(shift_workers):
                worker_shifts.append(
                    models.WorkerShift(
                        worker=workers[sw],
                        shift=shift,
                        order=i + 1,
                    )
                )
    for workplace in workplaces.values():
        workplace.save()
    for worker in workers.values():
        worker.save()
    for shift in shifts:
        shift.workplace = shift.workplace
        shift.save()
    for worker_shift in worker_shifts:
        worker_shift.worker = worker_shift.worker
        worker_shift.shift = worker_shift.shift
        worker_shift.save()


def export_all_data():
    from shifts import models

    worker_name_to_id = {}
    worker_id_to_name = {}
    workers = {}
    for worker in models.Worker.objects.all():
        if worker.name in worker_name_to_id:
            n = next(
                n
                for n in ("%s%s" % (worker.name, i) for i in range(1000))
                if n not in worker_name_to_id
            )
        else:
            n = worker.name
        worker_name_to_id[n] = worker.id
        worker_id_to_name[worker.id] = n
        w = workers[n] = {}
        if n != worker.name:
            w["name"] = worker.name
        if worker.phone:
            w["phone"] = worker.phone
        if worker.login_secret:
            w["login_secret"] = worker.login_secret
        if worker.cookie_secret:
            w["cookie_secret"] = worker.cookie_secret
    workplace_name_to_id = {}
    workplace_id_to_name = {}
    workplaces = {}
    for workplace in models.Workplace.objects.all():
        if workplace.name in workplace_name_to_id:
            n = next(
                n
                for n in ("%s%s" % (workplace.name, i) for i in range(1000))
                if n not in workplace_name_to_id
            )
        else:
            n = workplace.name
        workplace_name_to_id[n] = workplace.id
        workplace_id_to_name[workplace.id] = n
        wp = workplaces[n] = {}
        if n != workplace.name:
            wp["name"] = workplace.name
        wp["slug"] = workplace.slug
        wp.update(workplace.get_settings())
        wp["shifts"] = []
    shift_id_to_worker_list = {}
    for shift in models.Shift.objects.order_by("date", "order"):
        sh = shift.as_dict()
        workplaces[workplace_id_to_name[shift.workplace_id]]["shifts"].append(sh)
        sh["workers"] = shift_id_to_worker_list[shift.id] = []
    for ws in models.WorkerShift.objects.order_by("order"):
        shift_id_to_worker_list[ws.shift_id].append(worker_id_to_name[ws.worker_id])
    print(
        json.dumps(
            {
                "workers": workers,
                "workplaces": workplaces,
            },
            indent=2,
        )
    )


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
            wd: {
                "registration_deadline": "%sdT18:00" % (-3 - i),
                "shifts": ["DV", "AV", "NV"],
            }
            for i, wd in enumerate(models.WEEKDAYS)
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
