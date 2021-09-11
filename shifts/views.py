from django.http import HttpResponse
from django.views.generic import View


class ScheduleView(View):
    def get(self, request):
        return HttpResponse("Hello world!")


# ScheduleView (public)
# ScheduleEdit (admin)
# TodayView (internal)
# WorkerList (admin)
# - Login links to forward to workers
