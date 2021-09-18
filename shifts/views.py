import datetime
import json
from typing import List, Optional

from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import (
    Http404,
    HttpResponseBadRequest,
    HttpResponseRedirect,
    JsonResponse,
)
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
        assert isinstance(date, datetime.date)
        try:
            shift_id: Optional[int] = models.Shift.objects.values_list(
                "id", flat=True
            ).get(date=date, slug=form.cleaned_data["shift"])
        except models.Shift.DoesNotExist:
            shift_id = None
        if shift_id is None:
            ex: List[int] = []
        else:
            ex = list(
                models.WorkerShift.objects.values_list("id", flat=True).filter(
                    shift_id=shift_id, worker_id=worker.id
                )[:1]
            )
        if form.cleaned_data["register"]:
            if ex:
                return self.render_to_response(
                    self.get_context_data(**kwargs, form_error="Already registered")
                )
            if shift_id is None:
                workplace = models.Workplace.objects.all()[:1][0]
                workplace_settings = workplace.get_settings()
                shifts = models.day_shifts_for_settings(
                    date, workplace_settings, workplace
                )
                try:
                    (the_shift,) = [
                        shift
                        for shift in shifts
                        if shift.slug == form.cleaned_data["shift"]
                    ]
                except ValueError:
                    return self.render_to_response(
                        self.get_context_data(**kwargs, form_error="No such shift")
                    )
                for shift in shifts:
                    shift.save()
                shift_id = the_shift.id
                order = 1
            else:
                max_order = list(
                    models.WorkerShift.objects.values_list("order", flat=True)
                    .filter(shift_id=shift_id)
                    .order_by("-order")[:1]
                )
                order = max_order[0] + 1 if max_order else 1
            old_list = list(
                models.WorkerShift.objects.filter(shift_id=shift_id)
                .order_by("order")
                .values_list("worker__name")
            )
            ws = models.WorkerShift(worker=worker, order=order)
            ws.shift_id = shift_id
            ws.save()
        else:
            assert form.cleaned_data["unregister"]
            if not ex:
                return self.render_to_response(
                    self.get_context_data(**kwargs, form_error="Not registered")
                )
            old_list = list(
                models.WorkerShift.objects.filter(shift_id=shift_id)
                .order_by("order")
                .values_list("worker__name")
            )
            models.WorkerShift.objects.filter(id=ex[0]).delete()
        new_list = list(
            models.WorkerShift.objects.filter(shift_id=shift_id)
            .order_by("order")
            .values_list("worker__name")
        )
        workplace, shift_slug = models.Shift.objects.values_list(
            "workplace__slug", "slug"
        ).get(id=shift_id)
        models.Changelog.create_now(
            "register" if form.cleaned_data["register"] else "unregister",
            {
                "workplace": workplace,
                "date": str(date),
                "shift": shift_slug,
                "old": old_list,
                "new": new_list,
            },
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
    def get(self, request):
        qs = models.Shift.objects.all()
        fromdate: Optional[datetime.date] = None
        untildate: Optional[datetime.date] = None
        if "fromdate" in request.GET:
            try:
                fromdate = datetime.datetime.strptime(
                    request.GET["fromdate"], "%Y-%m-%d"
                )
            except ValueError:
                return JsonResponse({"error": "bad fromdate"}, status_code=400)
        if "untildate" in request.GET:
            try:
                untildate = datetime.datetime.strptime(
                    request.GET["untildate"], "%Y-%m-%d"
                )
            except ValueError:
                return JsonResponse({"error": "bad untildate"}, status_code=400)
        if "week" in request.GET:
            monday = monday_from_week_string(request.GET["week"])
            if monday is None:
                return JsonResponse({"error": "bad week"}, status_code=400)
            else:
                fromdate = monday
                untildate = monday + datetime.timedelta(6)
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
        return JsonResponse({"rows": shifts_json})


class ApiShift(ApiMixin, View):
    pass


class ApiChangelog(ApiMixin, View):
    pass
