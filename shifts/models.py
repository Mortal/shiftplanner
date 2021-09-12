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


class ShiftSettings(TypedDict, total=False):
    registration_deadline: str


class Shift(models.Model):
    workplace = models.ForeignKey(Workplace, models.CASCADE)
    date = models.DateField()
    order = models.PositiveSmallIntegerField()
    slug = models.SlugField(max_length=150)
    name = models.CharField(max_length=150)
    settings = models.TextField(default="{}")

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


class WorkerShift(models.Model):
    worker = models.ForeignKey(Worker, models.CASCADE)
    shift = models.ForeignKey(Shift, models.CASCADE)
    order = models.PositiveSmallIntegerField()


class Changelog(models.Model):
    time = DateTimeUTCField()
    worker = models.ForeignKey(Worker, models.SET_NULL, blank=True, null=True)
    user = models.ForeignKey(User, models.SET_NULL, blank=True, null=True)
    kind = models.CharField(max_length=150)
    data = models.TextField(blank=True)


# Schedule
# - Registration deadline, workers per slot
# - Slug
# - Slots
# Slot in Schedule
# Worker in Slot
# - Order
# Changelog
# - Time
# - Worker
# - User
# - Kind
# - Data
