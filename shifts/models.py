import datetime
import json
import random
import string
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional, TypedDict

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

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
    phone = models.CharField(max_length=40, null=True, blank=True, db_index=True)
    login_secret = models.CharField(max_length=150, null=True, blank=True)
    cookie_secret = models.CharField(max_length=150, null=True, blank=True)

    def __str__(self) -> str:
        return self.name

    def get_or_save_cookie_secret(self) -> str:
        assert self.id is not None
        if self.cookie_secret is None:
            self.cookie_secret = "".join(
                random.choice(string.ascii_letters) for _ in range(40)
            )
            Worker.objects.filter(id=self.id).update(cookie_secret=self.cookie_secret)
        return f"{self.id}:{self.cookie_secret}"

    @classmethod
    def get_by_cookie_secret(self, s: str) -> "Optional[Worker]":
        if s.count(":") != 1:
            return None
        id_str, secret = s.split(":")
        try:
            id_int = int(id_str)
        except ValueError:
            return None
        try:
            return Worker.objects.get(id=id_int, cookie_secret=secret)
        except Worker.DoesNotExist:
            return None


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

    def as_dict(self) -> Any:
        return {
            "date": self.date.strftime("%Y-%m-%d"),
            "slug": self.slug,
            "name": self.name,
            **self.get_settings(),
        }

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


DAYS_OF_THE_WEEK = [
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
    wd = DAYS_OF_THE_WEEK[date.weekday()]
    try:
        day_settings = settings["weekday_defaults"][wd]
    except KeyError:
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

    @classmethod
    def create_now(
        cls,
        kind: str,
        data: Dict[str, Any],
        *,
        worker: Optional[Worker] = None,
        user: Optional[User] = None,
    ) -> None:
        cls.objects.create(
            time=timezone.now(),
            worker=worker,
            user=user,
            kind=kind,
            data=json.dumps(data),
        )
        print_data = {"kind": kind}
        if worker is not None:
            print_data["worker"] = worker.name
        if user is not None:
            print_data["user"] = user.username
        print(json.dumps({**print_data, **data}))
