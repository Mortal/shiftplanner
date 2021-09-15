import datetime
import json
from contextlib import contextmanager
from typing import Dict, Iterator, List, Optional, TypedDict

from django.contrib.auth.models import User
from django.db import models

from shifts.django_datetime_utc import DateTimeUTCField


class DaySettings(TypedDict):
    registration_deadline: str
    shifts: List[str]


class WorkplaceSettings(TypedDict, total=False):
    weekday_defaults: Dict[str, DaySettings]


class Workplace(models.Model):
    slug = models.SlugField(max_length=150)
    name = models.CharField(max_length=150)
    settings = models.TextField(default="{}")

    def __str__(self) -> str:
        return self.name

    def get_settings(self) -> WorkplaceSettings:
        return json.loads(self.settings)

    @contextmanager
    def update_settings(self) -> Iterator[WorkplaceSettings]:
        s = json.loads(self.settings)
        yield s
        self.settings = json.dumps(s)


class Worker(models.Model):
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=150, null=True, blank=True)
    login_secret = models.CharField(max_length=150, null=True, blank=True)
    cookie_secret = models.CharField(max_length=150, null=True, blank=True)

    def __str__(self) -> str:
        return self.name


class ShiftSettings(TypedDict, total=False):
    registration_deadline: str


class Shift(models.Model):
    workplace = models.ForeignKey(Workplace, models.CASCADE)
    date = models.DateField()
    order = models.PositiveSmallIntegerField()
    slug = models.SlugField(max_length=150)
    name = models.CharField(max_length=150)
    settings = models.TextField(default="{}")

    def __str__(self) -> str:
        return f"{self.date} {self.name}"

    def get_settings(self) -> ShiftSettings:
        return json.loads(self.settings)

    @contextmanager
    def update_settings(self) -> Iterator[ShiftSettings]:
        s = json.loads(self.settings)
        yield s
        self.settings = json.dumps(s)

    REGISTRATION_DEADLINE_FMT = "%Y-%m-%dT%H:%M:%S%z"

    @property
    def registration_deadline(self) -> Optional[datetime.datetime]:
        try:
            v = self.get_settings()["registration_deadline"]
        except KeyError:
            return None
        return datetime.datetime.strptime(v, self.REGISTRATION_DEADLINE_FMT)

    @registration_deadline.setter
    def registration_deadline(self, v: Optional[datetime.datetime]) -> None:
        with self.update_settings() as s:
            if v is None:
                s.pop("registration_deadline", None)
            else:
                assert v.tzinfo is not None
                s["registration_deadline"] = v.strftime(self.REGISTRATION_DEADLINE_FMT)


WEEKDAYS = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


def day_shifts_for_settings(
    date: datetime.date,
    settings: WorkplaceSettings,
    workplace: Optional[Workplace] = None,
) -> List[Shift]:
    wd = WEEKDAYS[date.weekday()]
    try:
        day_settings = settings["weekday_defaults"][wd]
    except KeyError:
        print("Nothing for %r in %r" % (wd, settings))
        return []
    assert day_settings["registration_deadline"].count("dT") == 1
    days_str, time = day_settings["registration_deadline"].split("dT")
    assert time.count(":") == 1
    days = int(days_str)
    assert days < 0
    h, m = map(int, time.split(":"))
    deadline = datetime.datetime.combine(
        date + datetime.timedelta(days), datetime.time(h, m)
    )
    shifts: List[Shift] = []
    for i, n in enumerate(day_settings["shifts"]):
        shift_settings = {
            "registration_deadline": deadline.strftime(Shift.REGISTRATION_DEADLINE_FMT)
        }
        shifts.append(
            Shift(
                workplace=workplace,
                date=date,
                order=i + 1,
                slug=n,
                name=n,
                settings=json.dumps(shift_settings),
            )
        )
    return shifts


class WorkerShift(models.Model):
    worker = models.ForeignKey(Worker, models.CASCADE)
    shift = models.ForeignKey(Shift, models.CASCADE)
    order = models.PositiveSmallIntegerField()


class Changelog(models.Model):
    time = DateTimeUTCField(db_index=True)
    worker = models.ForeignKey(Worker, models.SET_NULL, blank=True, null=True)
    user = models.ForeignKey(User, models.SET_NULL, blank=True, null=True)
    kind = models.CharField(max_length=150, db_index=True)
    data = models.TextField(blank=True)
