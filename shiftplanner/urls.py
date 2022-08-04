"""shiftplanner URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.contrib import admin
from django.urls import path
from django.views import defaults, static

import shifts.views

urlpatterns = [
    path("", shifts.views.HomeView.as_view()),
    path("s/<str:week>/", shifts.views.ScheduleView.as_view()),
    path("myshifts/", shifts.views.WorkerShiftListView.as_view()),
    path("admin/", shifts.views.AdminHomeView.as_view()),
    path("admin/s/<str:week>/", shifts.views.AdminScheduleView.as_view()),
    path("admin/s/<str:week>/print/", shifts.views.AdminPrintView.as_view()),
    path("admin/changelog/", shifts.views.AdminChangelogView.as_view()),
    path("admin/workers/", shifts.views.AdminWorkersView.as_view()),
    path("admin/shifts/", shifts.views.AdminShiftsView.as_view()),
    path("admin/settings/", shifts.views.AdminSettingsView.as_view()),
    path("admin/worker_stats/", shifts.views.AdminWorkerStatsView.as_view()),
    path("adminlogin/", shifts.views.AdminLoginView.as_view(), name="admin_login"),
    path("adminlogout/", shifts.views.AdminLogoutView.as_view(), name="admin_logout"),
    path("djangoadmin/", admin.site.urls),
    path("login/", shifts.views.WorkerLoginView.as_view(), name="worker_login"),
    path("logout/", shifts.views.WorkerLogoutView.as_view(), name="worker_logout"),
    path("static/<path:path>", static.serve, {"document_root": settings.STATIC_ROOT}),
    path("api/v0/changelog/", shifts.views.ApiChangelog.as_view()),
    path("api/v0/workplace/", shifts.views.ApiWorkplace.as_view()),
    path("api/v0/worker/", shifts.views.ApiWorkerList.as_view()),
    path("api/v0/worker_delete/", shifts.views.ApiWorkerDelete.as_view()),
    path("api/v0/worker/<int:id>/", shifts.views.ApiWorker.as_view()),
    path("api/v0/worker_stats/", shifts.views.ApiWorkerStats.as_view()),
    path("api/v0/shift/", shifts.views.ApiShiftList.as_view()),
    path("api/v0/shift_delete/", shifts.views.ApiWorkerShiftDataDelete.as_view()),
    path("api/v0/shift/<str:date>/<str:slug>/", shifts.views.ApiShift.as_view()),
    path("api/v0/export/", shifts.views.ApiExport.as_view()),
] + [
    path(p, shifts.views.silent_page_not_found)
    for p in """
    apple-touch-icon-120x120-precomposed.png
    apple-touch-icon-120x120.png
    apple-touch-icon-precomposed.png
    apple-touch-icon.png
    favicon.ico
    """.split()
]
