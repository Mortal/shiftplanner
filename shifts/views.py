import datetime

from django.http import Http404, HttpResponse
from django.views.generic import TemplateView, View

from . import models
from .util import get_isocalender


class HomeView(View):
    def get(self, request):
        return HttpResponse("Hello world!")


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
        monday = get_isocalender(year, weekno, 0)
        dates = [monday + datetime.timedelta(d) for d in range(7)]
        shift_qs = models.Shift.objects.filter(date__in=dates)
        shift_qs = shift_qs.order_by("date", "order")
        shift_id_to_worker_list = {}
        weekdays = []
        for d in dates:
            d_shifts = []
            for s in shift_qs:
                if s.date != d:
                    continue
                shift_dict = s.as_dict()
                shift_dict["workers"] = shift_id_to_worker_list[s.id] = []
                d_shifts.append(shift_dict)
            weekdays.append({"date": d, "shifts": d_shifts})
        ws_qs = models.WorkerShift.objects.filter(
            shift_id__in=shift_id_to_worker_list.keys()
        )
        ws_qs = ws_qs.values_list("shift_id", "worker__name")
        for shift_id, worker_name in ws_qs.order_by("order"):
            shift_id_to_worker_list[shift_id].append(worker_name)
        return {"weekdays": weekdays}


# ScheduleView (public)
# ScheduleEdit (admin)
# TodayView (internal)
# WorkerList (admin)
# - Login links to forward to workers
