import datetime
import json
import random
import string
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional, Tuple, TypedDict

from django.contrib.auth.models import User
from django.db import connection, models
from django.utils import timezone

from shifts.django_datetime_utc import DateTimeUTCField


class DaySettings(TypedDict):
    registration_starts: str
    registration_deadline: str
    shifts: List[str]


class WorkplaceSettings(TypedDict, total=False):
    weekday_defaults: Dict[str, DaySettings]
    default_view_day: str
    message_of_the_day: str
    print_header_text: str
    max_print_per_shift: int
    login_email_template: str
    login_email_subject: str
    login_sms_template: str
    country_code: str


def add_string_duration(date: datetime.date, duration: str) -> datetime.datetime:
    assert duration.count("dT") == 1
    days_str, time = duration.split("dT")
    assert time.count(":") == 1
    days = int(days_str)
    assert days < 0
    h, m = map(int, time.split(":"))
    return timezone.make_aware(
        datetime.datetime.combine(date + datetime.timedelta(days), datetime.time(h, m))
    )


def validate_string_duration(duration: str) -> str:
    if duration.count("dT") != 1:
        raise ValueError("duration must contain 'dT'")
    days_str, time = duration.split("dT")
    if time.count(":") != 1:
        raise ValueError("duration time must contain one ':'")
    try:
        days = int(days_str)
    except Exception:
        raise ValueError("duration days must be integer") from None
    if days >= 0:
        raise ValueError("duration days must be negative")
    try:
        h, m = map(int, time.split(":"))
        datetime.time(h, m)
    except Exception:
        raise ValueError("duration time must be HH:MM")
    return duration


def validate_shift(s: str) -> str:
    s = " ".join(s.split())
    if not s:
        raise ValueError("shift must not be the empty string")
    return s


def validate_day_settings(v: Any) -> DaySettings:
    if not isinstance(v, dict):
        raise ValueError("day_settings must be dict")
    unk = set(v.keys()) - set(DaySettings.__annotations__.keys())
    missing = set(DaySettings.__annotations__.keys()) - set(v.keys())
    if unk:
        raise ValueError("Unknown day_settings keys %s" % ",".join(sorted(unk)))
    if missing:
        raise ValueError("Missing day_settings keys %s" % ",".join(sorted(missing)))
    shifts = v["shifts"]
    if not shifts:
        raise ValueError("shifts must not be empty")
    if not all(isinstance(s, str) for s in shifts):
        raise ValueError("shifts must be str")
    if len(shifts) != len(set(shifts)):
        raise ValueError("shifts must be distinct")
    return {
        "registration_starts": validate_string_duration(v["registration_starts"]),
        "registration_deadline": validate_string_duration(v["registration_deadline"]),
        "shifts": [validate_shift(s) for s in shifts],
    }


def validate_weekday_defaults(v: Any) -> Dict[str, DaySettings]:
    if not isinstance(v, dict):
        raise ValueError("weekday_defaults must be dict")
    unk = set(v.keys()) - set(DAYS_OF_THE_WEEK)
    if unk:
        raise ValueError("Unknown weekday_defaults keys %s" % ",".join(sorted(unk)))
    return {k: validate_day_settings(d) for k, d in v.items()}


def validate_default_view_day(v: str) -> str:
    if not v.endswith("d"):
        raise ValueError("default_view_day must end with 'd'")
    try:
        i = int(v[:-1])
    except Exception:
        raise ValueError("default_view_day must be NUMBER 'd'")
    if not -100 <= i <= 100:
        raise ValueError("default_view_day out of range")
    return "%sd" % (i,)


def validate_workplace_settings(settings: Dict[str, Any]) -> WorkplaceSettings:
    unk = set(settings.keys()) - set(WorkplaceSettings.__annotations__.keys())
    if unk:
        raise ValueError("Unknown keys: %s" % ",".join(sorted(unk)))
    res = WorkplaceSettings()
    if "weekday_defaults" in settings:
        res["weekday_defaults"] = validate_weekday_defaults(
            settings["weekday_defaults"]
        )
    if "default_view_day" in settings:
        v = settings["default_view_day"]
        if not isinstance(v, str):
            raise ValueError("default_view_day must be str")
        res["default_view_day"] = validate_default_view_day(v)
    if "message_of_the_day" in settings:
        v = settings["message_of_the_day"]
        if not isinstance(v, str):
            raise ValueError("message_of_the_day must be str")
        res["message_of_the_day"] = v
    if "print_header_text" in settings:
        v = settings["print_header_text"]
        if not isinstance(v, str):
            raise ValueError("print_header_text must be str")
        res["print_header_text"] = v
    if "max_print_per_shift" in settings:
        i = settings["max_print_per_shift"]
        if not isinstance(i, int):
            raise ValueError("max_print_per_shift must be int")
        res["max_print_per_shift"] = i
    if "login_email_template" in settings:
        v = settings["login_email_template"]
        if not isinstance(v, str):
            raise ValueError("login_email_template must be str")
        res["login_email_template"] = v
    if "login_email_subject" in settings:
        v = settings["login_email_subject"]
        if not isinstance(v, str):
            raise ValueError("login_email_subject must be str")
        res["login_email_subject"] = v
    if "login_sms_template" in settings:
        v = settings["login_sms_template"]
        if not isinstance(v, str):
            raise ValueError("login_sms_template must be str")
        res["login_sms_template"] = v
    if "country_code" in settings:
        v = settings["country_code"]
        if not isinstance(v, str):
            raise ValueError("country_code must be str")
        res["country_code"] = v
    return res


def compute_default_week(
    settings: WorkplaceSettings, today: datetime.date
) -> Tuple[int, int]:
    default_view_day_str = str(settings.get("default_view_day") or "0d")
    if default_view_day_str.endswith("d"):
        default_view_day_str = default_view_day_str.rpartition("d")[0]
    try:
        default_view_day = int(default_view_day_str)
    except ValueError:
        default_view_day = 0
    date = today + datetime.timedelta(default_view_day)
    isocal = date.isocalendar()
    return (isocal.year, isocal.week)


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

    class Meta:
        permissions = [
            ("api", "Can access the admin panel and the admin API"),
        ]


def random_secret(n: int) -> str:
    return "".join(random.choice(string.ascii_letters) for _ in range(n))


class Worker(models.Model):
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=40, null=True, blank=True, db_index=True)
    login_secret = models.CharField(max_length=150, null=True, blank=True)
    cookie_secret = models.CharField(max_length=150, null=True, blank=True)
    active = models.BooleanField(blank=True, default=True)
    note = models.TextField(blank=True)

    def __str__(self) -> str:
        return self.name

    def get_or_save_cookie_secret(self) -> str:
        assert self.id is not None
        if self.cookie_secret is None:
            self.cookie_secret = random_secret(40)
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
            return Worker.objects.get(id=id_int, cookie_secret=secret, active=True)
        except Worker.DoesNotExist:
            return None


class ShiftSettings(TypedDict, total=False):
    registration_starts: str
    registration_deadline: str


class Shift(models.Model):
    workplace = models.ForeignKey(Workplace, models.CASCADE)
    date = models.DateField(db_index=True)
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

    DATETIME_FMT = "%Y-%m-%dT%H:%M:%S%z"

    @property
    def registration_starts(self) -> Optional[datetime.datetime]:
        try:
            v = self.get_settings()["registration_starts"]
        except KeyError:
            return None
        return datetime.datetime.strptime(v, Shift.DATETIME_FMT)

    @registration_starts.setter
    def registration_starts(self, v: Optional[datetime.datetime]) -> None:
        with self.update_settings() as s:
            if v is None:
                s.pop("registration_starts", None)
            else:
                assert v.tzinfo is not None
                s["registration_starts"] = v.strftime(Shift.DATETIME_FMT)

    @property
    def registration_deadline(self) -> Optional[datetime.datetime]:
        try:
            v = self.get_settings()["registration_deadline"]
        except KeyError:
            return None
        return datetime.datetime.strptime(v, Shift.DATETIME_FMT)

    @registration_deadline.setter
    def registration_deadline(self, v: Optional[datetime.datetime]) -> None:
        with self.update_settings() as s:
            if v is None:
                s.pop("registration_deadline", None)
            else:
                assert v.tzinfo is not None
                s["registration_deadline"] = v.strftime(Shift.DATETIME_FMT)


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
    registration_starts = add_string_duration(date, day_settings["registration_starts"])
    registration_deadline = add_string_duration(
        date, day_settings["registration_deadline"]
    )
    shifts: List[Shift] = []
    for i, n in enumerate(day_settings["shifts"]):
        shift_settings = {
            "registration_starts": registration_starts.strftime(Shift.DATETIME_FMT),
            "registration_deadline": registration_deadline.strftime(Shift.DATETIME_FMT),
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


class WorkerShiftComment(models.Model):
    worker = models.ForeignKey(Worker, models.CASCADE)
    shift = models.ForeignKey(Shift, models.CASCADE)
    comment = models.TextField()


def get_current_worker_stats():
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
            `w`.`id`,
            `w`.`name`,
            `w`.`active`,
            (STRFTIME('%j', DATE(`s`.`date`, '-3 days', 'weekday 4')) - 1) / 7 + 1 AS `the_week`,
            STRFTIME('%Y%m', `s`.`date`) AS `the_month`,
            COUNT(`ws`.`id`)
            FROM `shifts_worker` AS `w`
            LEFT JOIN `shifts_workershift` AS `ws`
            ON `ws`.`worker_id` = `w`.`id`
            LEFT JOIN `shifts_shift` AS `s`
            ON `ws`.`shift_id` = `s`.`id`
            GROUP BY
            `w`.`id`, `the_week`, `the_month`
            ORDER BY `w`.`id`
            """
        )
        rows = sorted(cursor.fetchall())
    result: List[Any] = []
    for worker_id, worker_name, active, isoweek, yyyymm, count in rows:
        if not result or result[-1]["id"] != worker_id:
            result.append(
                {"id": worker_id, "name": worker_name, "active": active, "stats": []}
            )
        if not count:
            continue
        year = int(yyyymm[:4])
        month = int(yyyymm[4:])
        if isoweek > 50 and month == 1:
            isoyear = year - 1
        elif isoweek < 5 and month == 12:
            isoyear = year + 1
        else:
            isoyear = year
        result[-1]["stats"].append(
            {
                "isoyear": isoyear,
                "isoweek": isoweek,
                "year": year,
                "month": month,
                "count": count,
            }
        )
    result.sort(key=lambda r: r["name"])
    return result


class WorkerShiftAggregateCount(models.Model):
    worker = models.ForeignKey(Worker, models.SET_NULL, blank=True, null=True)
    isoyearweek = models.PositiveSmallIntegerField(db_index=True)
    yearmonth = models.PositiveSmallIntegerField(db_index=True)
    count = models.IntegerField()


def get_worker_stats():
    qs = WorkerShiftAggregateCount.objects.exclude(worker=None)
    qsvals = qs.values_list("worker_id", "isoyearweek", "yearmonth", "count")
    res = get_current_worker_stats()
    return compute_worker_stats(qsvals, res)


def compute_worker_stats(qsvals, res):
    prev_counts = {}
    for worker, isoyearweek, yearmonth, count in qsvals:
        x = prev_counts.setdefault(worker, {})
        k = isoyearweek, yearmonth
        x[k] = x.get(k, 0) + count
    for w in res:
        try:
            x = prev_counts[w["id"]]
        except KeyError:
            continue
        for s in w["stats"]:
            k = 100 * s["isoyear"] + s["isoweek"], 100 * s["year"] + s["month"]
            x.pop(k, None)
        for (isoyearweek, yearmonth), count in x.items():
            isoyear, isoweek = divmod(isoyearweek, 100)
            year, month = divmod(yearmonth, 100)
            w["stats"].append(
                {
                    "isoyear": isoyear,
                    "isoweek": isoweek,
                    "year": year,
                    "month": month,
                    "count": count,
                }
            )
    return res


def prepare_update_worker_shift_aggregate_count():
    current_counts = {}
    for w in get_current_worker_stats():
        for s in w["stats"]:
            k = w["id"], 100 * s["isoyear"] + s["isoweek"], 100 * s["year"] + s["month"]
            current_counts[k] = current_counts.get(k, 0) + s["count"]
    minisoyearweek = min(
        isoyearweek for worker, isoyearweek, yearmonth in current_counts
    )
    minyearmonth = min(yearmonth for worker, isoyearweek, yearmonth in current_counts)
    qs = WorkerShiftAggregateCount.objects.filter(
        isoyearweek__gte=minisoyearweek
    ) | WorkerShiftAggregateCount.objects.filter(yearmonth__gte=minyearmonth)
    qs = qs.exclude(worker=None)
    prev_counts = {}
    prev_count_id = {}
    qsvals = qs.values_list("id", "worker_id", "isoyearweek", "yearmonth", "count")
    for i, worker, isoyearweek, yearmonth, count in qsvals:
        k = worker, isoyearweek, yearmonth
        if k not in current_counts:
            continue
        prev_counts[k] = prev_counts.get(k, 0) + count
        prev_count_id[k] = i
    add_counts = []
    stat_pos = 0
    stat_nul = 0
    stat_neg = 0
    for k, c in current_counts.items():
        d = c - prev_counts.get(k, 0)
        if not d:
            stat_nul += 1
            continue
        if d < 0:
            stat_neg += 1
        else:
            stat_pos += 1
        add_counts.append((k, prev_count_id.get(k), d))
    return (stat_pos, stat_nul, stat_neg, add_counts)


def do_update_worker_shift_aggregate_count(add_counts):
    for k, row_id, count in add_counts:
        worker, isoyearweek, yearmonth = k
        if row_id is None:
            WorkerShiftAggregateCount.objects.create(
                worker_id=worker,
                isoyearweek=isoyearweek,
                yearmonth=yearmonth,
                count=count,
            )
        else:
            qs = WorkerShiftAggregateCount.objects.filter(id=row_id)
            # assert qs.values_list("worker_id", "isoyearweek", "yearmonth").get() == (
            #     worker,
            #     isoyearweek,
            #     yearmonth,
            # )
            qs.update(count=F("count") + count)


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
