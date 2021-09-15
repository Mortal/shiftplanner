import datetime
import json

from django.http import Http404, HttpResponseRedirect
from django.views.generic import FormView, TemplateView

from . import forms, models
from .util import get_isocalender


class HomeView(TemplateView):
    template_name = "shifts/home.html"

    def get_context_data(self):
        cookie = self.request.COOKIES.get("shiftplannerlogin", "")
        worker = models.Worker.get_by_cookie_secret(cookie)
        return {"cookie": cookie, "worker": worker}


class ScheduleView(TemplateView):
    template_name = "shifts/schedule.html"

    def get_context_data(self, **kwargs):
        week = kwargs["week"]
        try:
            year, weekno = map(int, week.split("w"))
        except ValueError:
            raise Http404
        if not 1900 < year < 2100 or week != f"{year}w{weekno}":
            raise Http404
        try:
            monday = get_isocalender(year, weekno, 0)
        except ValueError:
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
        for s in shift_qs.values("id", "date", "name"):
            s_id = s.pop("id")
            s_date = s.pop("date")
            s["workers"] = shift_id_to_worker_list[s_id] = []
            shifts_for_date[s_date].append(s)
        workplace_settings = json.loads(
            models.Workplace.objects.values_list("settings", flat=True)[:1][0]
        )
        ws_qs = models.WorkerShift.objects.filter(
            shift_id__in=shift_id_to_worker_list.keys()
        )
        ws_qs = ws_qs.values_list("shift_id", "worker__name")
        for shift_id, worker_name in ws_qs.order_by("order"):
            shift_id_to_worker_list[shift_id].append(worker_name)
        for s_date in shifts_for_date:
            if shifts_for_date[s_date]:
                continue
            for s in models.day_shifts_for_settings(s_date, workplace_settings):
                shifts_for_date[s_date].append({"name": s.name, "workers": []})
        return {
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
