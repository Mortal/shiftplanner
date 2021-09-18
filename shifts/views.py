import datetime
import json
from typing import Any, Dict, List, Optional, Tuple

from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.auth.models import User
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.views.generic import FormView, TemplateView, View

from . import forms, models
from .util import get_isocalender


class HomeView(TemplateView):
    template_name = "shifts/home.html"

    def get_context_data(self):
        cookie = self.request.COOKIES.get("shiftplannerlogin", "")
        worker = models.Worker.get_by_cookie_secret(cookie)
        return {"cookie": cookie, "worker": worker}


def monday_from_week_string(week: str) -> Optional[datetime.date]:
    try:
        year, weekno = map(int, week.split("w"))
    except ValueError:
        return None
    if not 1900 < year < 2100 or week != f"{year}w{weekno}":
        return None
    try:
        return get_isocalender(year, weekno, 0)
    except ValueError:
        return None


class ShiftUpdater:
    shift_id: Optional[int]
    old_ones: List[Dict[str, Any]]

    def get_or_create_shift_id(
        self, workplace: models.Workplace, date: datetime.date, slug: str
    ) -> Optional[int]:
        if self.shift_id is not None:
            return self.shift_id
        workplace_settings = workplace.get_settings()
        shifts = models.day_shifts_for_settings(date, workplace_settings, workplace)
        try:
            (the_shift,) = [shift for shift in shifts if shift.slug == slug]
        except ValueError:
            return None
        for shift in shifts:
            shift.save()
        self.shift_id = the_shift.id
        return the_shift.id

    def create_changelog_entry(
        self,
        action: str,
        *,
        worker: Optional[models.Worker] = None,
        user: Optional[User] = None,
    ) -> None:
        old_list: List[str] = [o["worker__name"] for o in self.old_ones]
        new_list = list(
            models.WorkerShift.objects.filter(shift_id=self.shift_id)
            .order_by("order")
            .values_list("worker__name", flat=True)
        )
        date, workplace, shift_slug = models.Shift.objects.values_list(
            "date", "workplace__slug", "slug"
        ).get(id=self.shift_id)
        models.Changelog.create_now(
            action,
            {
                "workplace": workplace,
                "date": str(date),
                "shift": shift_slug,
                "old": old_list,
                "new": new_list,
            },
            worker=worker,
            user=user,
        )


def prepare_shift_update(date: datetime.date, slug: str) -> ShiftUpdater:
    upd = ShiftUpdater()
    assert isinstance(date, datetime.date)
    try:
        upd.shift_id = models.Shift.objects.values_list("id", flat=True).get(
            date=date, slug=slug
        )
    except models.Shift.DoesNotExist:
        upd.shift_id = None
    if upd.shift_id is None:
        upd.old_ones = []
    else:
        upd.old_ones = list(
            models.WorkerShift.objects.filter(shift_id=upd.shift_id)
            .order_by("order")
            .values("id", "worker_id", "worker__name", "order")
        )
    return upd


class ScheduleView(TemplateView):
    template_name = "shifts/schedule.html"

    def post(self, request, **kwargs):
        cookie = self.request.COOKIES.get("shiftplannerlogin", "")
        worker = models.Worker.get_by_cookie_secret(cookie)
        if not worker:
            return self.render_to_response(
                self.get_context_data(**kwargs, form_error="Not logged in")
            )

        form = forms.RegisterForm(data=self.request.POST)
        if not form.is_valid():
            return self.render_to_response(
                self.get_context_data(**kwargs, form_error=str(form.errors))
            )
        date = form.cleaned_data["date"]
        slug = form.cleaned_data["shift"]
        upd = prepare_shift_update(date, slug)
        ex: List[int] = [o["id"] for o in upd.old_ones if o["worker_id"] == worker.id]
        if form.cleaned_data["register"]:
            if ex:
                return self.render_to_response(
                    self.get_context_data(**kwargs, form_error="Already registered")
                )
            workplace = models.Workplace.objects.all()[:1][0]
            shift_id = upd.get_or_create_shift_id(workplace, date, slug)
            if shift_id is None:
                return self.render_to_response(
                    self.get_context_data(**kwargs, form_error="No such shift")
                )
            if upd.old_ones:
                order = 1 + max(o["order"] for o in upd.old_ones)
            else:
                order = 1
            ws = models.WorkerShift(worker=worker, order=order)
            ws.shift_id = shift_id
            ws.save()
        else:
            assert form.cleaned_data["unregister"]
            if not ex:
                return self.render_to_response(
                    self.get_context_data(**kwargs, form_error="Not registered")
                )
            models.WorkerShift.objects.filter(id=ex[0]).delete()
        upd.create_changelog_entry(
            "register" if form.cleaned_data["register"] else "unregister",
            worker=worker,
        )
        return HttpResponseRedirect(self.request.path)

    def get_context_data(self, **kwargs):
        cookie = self.request.COOKIES.get("shiftplannerlogin", "")
        worker = models.Worker.get_by_cookie_secret(cookie)

        monday = monday_from_week_string(kwargs["week"])
        if monday is None:
            raise Http404
        dates = [monday + datetime.timedelta(d) for d in range(7)]

        prev_monday = (dates[0] - datetime.timedelta(7)).isocalendar()
        prev_url = f"../{prev_monday.year}w{prev_monday.week}/"
        next_monday = (dates[0] + datetime.timedelta(7)).isocalendar()
        next_url = f"../{next_monday.year}w{next_monday.week}/"

        shift_qs = models.Shift.objects.filter(date__in=dates)
        shift_qs = shift_qs.order_by("date", "order")
        shift_id_to_worker_list = {}
        weekdays = []
        shifts_for_date = {}
        for d in dates:
            d_shifts = shifts_for_date[d] = []
            weekdays.append({"date": d, "shifts": d_shifts})
        for s in shift_qs.values("id", "date", "name", "slug"):
            s_id = s.pop("id")
            s_date = s.pop("date")
            s["workers"] = []
            shift_id_to_worker_list[s_id] = s
            shifts_for_date[s_date].append(s)
        workplace_settings = json.loads(
            models.Workplace.objects.values_list("settings", flat=True)[:1][0]
        )
        ws_qs = models.WorkerShift.objects.filter(
            shift_id__in=shift_id_to_worker_list.keys()
        )
        ws_qs = ws_qs.values_list("shift_id", "worker_id", "worker__name")
        my_id = worker.id if worker else None
        for shift_id, worker_id, worker_name in ws_qs.order_by("order"):
            me = my_id == worker_id
            shift_id_to_worker_list[shift_id]["workers"].append(
                {"me": me, "name": worker_name}
            )
            if me:
                shift_id_to_worker_list[shift_id]["me"] = True
        for s_date in shifts_for_date:
            if shifts_for_date[s_date]:
                continue
            for s in models.day_shifts_for_settings(s_date, workplace_settings):
                shifts_for_date[s_date].append(
                    {"name": s.name, "slug": s.slug, "workers": []}
                )
        year, weekno, _ = monday.isocalendar()
        return {
            "form_error": kwargs.get("form_error"),
            "worker": worker,
            "next": next_url,
            "prev": prev_url,
            "week": weekno,
            "year": year,
            "weekdays": weekdays,
        }


class LoginView(FormView):
    form_class = forms.LoginForm
    template_name = "shifts/login.html"

    def form_valid(self, form):
        try:
            worker = models.Worker.objects.get(phone=form.cleaned_data["phone"])
        except models.Worker.DoesNotExist:
            form.add_error("phone", "Ingen bruger fundet")
            return self.form_invalid(form)
        if worker.login_secret != form.cleaned_data["password"]:
            form.add_error("phone", "Forkert kodeord")
            return self.form_invalid(form)
        resp = HttpResponseRedirect("/")
        resp.set_cookie(
            "shiftplannerlogin",
            worker.get_or_save_cookie_secret(),
            max_age=60 * 24 * 3600 if form.cleaned_data["remember_me"] else None,
            secure=True,
            httponly=True,
            samesite="Strict",
        )
        return resp


# ScheduleEdit (admin)
# TodayView (internal)
# WorkerList (admin)
# - Login links to forward to workers


class ApiMixin(PermissionRequiredMixin):
    permission_required = "shifts.api"


class ApiWorkerList(ApiMixin, View):
    def get(self, request):
        worker_fields = ["id", "name", "phone", "login_secret"]
        workers = list(models.Worker.objects.values(*worker_fields))
        return JsonResponse({"fields": worker_fields, "rows": workers})


class ApiWorker(ApiMixin, View):
    def get(self, request, id):
        worker_fields = ["id", "name", "phone", "login_secret"]
        try:
            worker = models.Worker.objects.values(worker_fields).get(id=id)
        except models.Worker.DoesNotExist:
            raise Http404
        fields = ["order", "shift__date", "shift__order", "shift__slug", "shift__name"]
        shifts = models.WorkerShift.objects.filter(worker_id=worker["id"])
        shifts_list = list(shifts.values(*fields))
        return JsonResponse(
            {"row": worker, "shifts": {"fields": fields, "rows": shifts_list}}
        )


class ApiShiftList(ApiMixin, View):
    def get_filter(
        self,
    ) -> Tuple[
        Optional[datetime.date], Optional[datetime.date], Optional[datetime.date]
    ]:
        fromdate: Optional[datetime.date] = None
        untildate: Optional[datetime.date] = None
        monday: Optional[datetime.date] = None
        if "fromdate" in self.request.GET:
            try:
                fromdate = datetime.datetime.strptime(
                    self.request.GET["fromdate"], "%Y-%m-%d"
                )
            except ValueError:
                raise ValueError("bad fromdate")
        if "untildate" in self.request.GET:
            try:
                untildate = datetime.datetime.strptime(
                    self.request.GET["untildate"], "%Y-%m-%d"
                )
            except ValueError:
                raise ValueError("bad untildate")
        if "week" in self.request.GET:
            monday = monday_from_week_string(self.request.GET["week"])
            if monday is None:
                raise ValueError("bad week")
            else:
                fromdate = monday
                untildate = monday + datetime.timedelta(6)
        return fromdate, untildate, monday

    def add_default_shifts(
        self, shifts_db: List[Any], fromdate: datetime.date, untildate: datetime.date
    ) -> None:
        workplace_settings = json.loads(
            models.Workplace.objects.values_list("settings", flat=True)[:1][0]
        )
        seen_dates = set(row["date"] for row in shifts_db)
        for i in range(1 + (untildate - fromdate).days):
            d = fromdate + datetime.timedelta(i)
            if d in seen_dates:
                continue
            for s in models.day_shifts_for_settings(d, workplace_settings):
                shifts_db.append(
                    {
                        "id": None,
                        "date": d,
                        "order": s.order,
                        "slug": s.slug,
                        "name": s.name,
                        "settings": s.settings,
                    }
                )

    def get(self, request):
        qs = models.Shift.objects.all()
        try:
            fromdate, untildate, monday = self.get_filter()
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=400)
        if fromdate is not None:
            qs = qs.filter(date__gte=fromdate)
        if untildate is not None:
            qs = qs.filter(date__lte=untildate)
        workers_qs = models.WorkerShift.objects.filter(shift__in=qs)
        workers_db = workers_qs.values_list(
            "shift_id", "order", "worker_id", "worker__name"
        )
        workers_db = workers_db.order_by("shift_id", "order")
        shifts_db = list(qs.values("id", "date", "order", "slug", "name", "settings"))
        if fromdate is not None and untildate is not None:
            self.add_default_shifts(shifts_db, fromdate, untildate)
        shifts_db.sort(key=lambda s: (s["date"], s["order"]))
        shifts_json = [
            {
                **row,
                "date": row["date"].strftime("%Y-%m-%d"),
                "settings": json.loads(row["settings"]),
                "workers": [],
            }
            for row in shifts_db
        ]
        shifts_by_id = {s["id"]: s for s in shifts_json if s["id"] is not None}
        for shift_id, order, worker_id, worker_name in workers_db:
            shifts_by_id[shift_id]["workers"].append(
                {"id": worker_id, "name": worker_name}
            )
        result = {"rows": shifts_json}
        if monday is not None:
            prev_monday = (monday - datetime.timedelta(7)).isocalendar()
            result["prev"] = f"{prev_monday.year}w{prev_monday.week}"
            next_monday = (monday + datetime.timedelta(7)).isocalendar()
            result["next"] = f"{next_monday.year}w{next_monday.week}"
        return JsonResponse(result)


class ApiShift(ApiMixin, View):
    def post(self, request, **kwargs):
        date_str: str = kwargs["date"]
        slug: str = kwargs["slug"]
        try:
            date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            raise Http404
        upd = prepare_shift_update(date, slug)
        workplace = models.Workplace.objects.all()[:1][0]
        shift_id = upd.get_or_create_shift_id(workplace, date, slug)
        if shift_id is None:
            raise Http404
        try:
            data = json.loads(request.body.decode("utf-8"))
        except Exception:
            return JsonResponse({"error": "expected JSON body"}, status=400)
        workers = data["workers"]
        common_prefix = 0
        while (
            common_prefix < len(upd.old_ones)
            and common_prefix < len(workers)
            and upd.old_ones[common_prefix]["worker_id"] == workers[common_prefix]["id"]
        ):
            common_prefix += 1
        to_delete = upd.old_ones[common_prefix:]
        to_insert = workers[common_prefix:]
        to_delete_qs = models.WorkerShift.objects.filter(
            id__in=[o["id"] for o in to_delete]
        )
        start_order = (
            (1 + upd.old_ones[common_prefix - 1]["order"]) if common_prefix else 1
        )
        to_insert_models = [
            models.WorkerShift(
                worker_id=o["id"],
                shift_id=shift_id,
                order=start_order + i,
            )
            for i, o in enumerate(to_insert)
        ]
        if to_delete:
            del_count = to_delete_qs.count()
            if del_count != len(to_delete):
                return JsonResponse(
                    {
                        "error": f"internal error (expected {len(to_delete)} to delete but got {del_count})"
                    },
                    status=500,
                )
            to_delete_qs.delete()
        models.WorkerShift.objects.bulk_create(to_insert_models)
        upd.create_changelog_entry(
            "edit",
            user=request.user,
        )
        return JsonResponse(
            {
                "ok": True,
                "debug": {
                    "common_prefix": common_prefix,
                    "to_delete": to_delete,
                    "to_insert": to_insert,
                },
            }
        )


class ApiChangelog(ApiMixin, View):
    pass


class AdminView(ApiMixin, TemplateView):
    template_name = "shifts/schedule_edit.html"
