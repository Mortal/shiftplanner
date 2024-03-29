import datetime
import itertools
import json
import typing
import urllib.parse
from typing import Any, Dict, List, Optional, Set, Tuple

from django.conf import settings
from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.auth.models import User
from django.http import (
    Http404,
    HttpResponseNotFound,
    HttpResponseRedirect,
    JsonResponse,
)
from django.templatetags.static import static
from django.utils import timezone
from django.utils.safestring import SafeString
from django.views.generic import FormView, TemplateView, View

from . import forms, models
from .util import get_isocalendar


class HomeView(View):
    def get(self, request):
        workplace = models.Workplace.objects.all()[:1][0]
        year, week = models.compute_default_week(
            workplace.get_settings(), datetime.date.today()
        )
        return HttpResponseRedirect("/s/%sw%s/" % (year, week))


class ApiMixin(PermissionRequiredMixin):
    permission_required = "shifts.api"

    def handle_no_permission(self):
        return HttpResponseRedirect("/adminlogin/")


class AdminHomeView(ApiMixin, View):
    def get(self, request):
        workplace = models.Workplace.objects.all()[:1][0]
        year, week = models.compute_default_week(
            workplace.get_settings(), datetime.date.today()
        )
        return HttpResponseRedirect("/admin/s/%sw%s/" % (year, week))


def monday_from_week_string(week: str) -> Optional[datetime.date]:
    try:
        year, weekno = map(int, week.split("w"))
    except ValueError:
        return None
    if not 1900 < year < 2100 or week != f"{year}w{weekno}":
        return None
    try:
        return get_isocalendar(year, weekno, 0)
    except ValueError:
        return None


def compute_is_registration_open(
    settings: models.ShiftSettings, now: datetime.datetime
) -> bool:
    registration_starts = datetime.datetime.strptime(
        settings["registration_starts"], models.Shift.DATETIME_FMT
    )
    registration_deadline = datetime.datetime.strptime(
        settings["registration_deadline"], models.Shift.DATETIME_FMT
    )
    return registration_starts < now < registration_deadline


class ShiftUpdater:
    workplace: models.Workplace
    date: datetime.date
    slug: str
    shift_id: Optional[int]
    shift_settings: Optional[Dict[str, Any]]
    old_ones: List[Dict[str, Any]]

    def get_or_create_shift_id(self) -> Optional[int]:
        if self.shift_id is not None:
            return self.shift_id
        workplace_settings = self.workplace.get_settings()
        shifts = models.day_shifts_for_settings(
            self.date, workplace_settings, self.workplace
        )
        try:
            (the_shift,) = [shift for shift in shifts if shift.slug == self.slug]
        except ValueError:
            return None
        for shift in shifts:
            shift.save()
        self.shift_id = the_shift.id
        self.shift_settings = the_shift.get_settings()
        return the_shift.id

    def is_registration_open(self, now: datetime.datetime) -> bool:
        if self.shift_settings is None:
            workplace_settings = self.workplace.get_settings()
            shifts = models.day_shifts_for_settings(
                self.date, workplace_settings, self.workplace
            )
            try:
                (the_shift,) = [shift for shift in shifts if shift.slug == self.slug]
            except ValueError:
                return False
            self.shift_settings = the_shift.get_settings()
        return compute_is_registration_open(self.shift_settings, now)

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
        models.Changelog.create_now(
            action,
            {
                "workplace": self.workplace.slug,
                "date": str(self.date),
                "shift": self.slug,
                "old": old_list,
                "new": new_list,
            },
            worker=worker,
            user=user,
        )


def prepare_shift_update(
    workplace: models.Workplace, date: datetime.date, slug: str
) -> ShiftUpdater:
    upd = ShiftUpdater()
    upd.workplace = workplace
    upd.date = date
    upd.slug = slug
    assert isinstance(date, datetime.date)
    try:
        upd.shift_id, settings = models.Shift.objects.values_list("id", "settings").get(
            date=date, slug=slug
        )
        upd.shift_settings = json.loads(settings)
    except models.Shift.DoesNotExist:
        upd.shift_id = None
        upd.shift_settings = None
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
        workplace = models.Workplace.objects.all()[:1][0]
        upd = prepare_shift_update(workplace, date, slug)
        ex: List[int] = [o["id"] for o in upd.old_ones if o["worker_id"] == worker.id]

        action = form.cleaned_data["action"]
        assert action in ("register", "unregister", "registercomment", "savecomment")
        shift_id: Optional[int] = None
        if action in ("register", "registercomment"):
            if ex:
                return self.render_to_response(
                    self.get_context_data(**kwargs, form_error="")
                )
            if not upd.is_registration_open(timezone.now()):
                return self.render_to_response(
                    self.get_context_data(
                        **kwargs, form_error="Tilmeldingen for denne uge er ikke åben."
                    )
                )
            shift_id = upd.get_or_create_shift_id()
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

            upd.create_changelog_entry(
                "register",
                worker=worker,
            )
        elif action == "unregister":
            if not ex:
                return self.render_to_response(
                    self.get_context_data(**kwargs, form_error="")
                )
            models.WorkerShift.objects.filter(id=ex[0]).delete()
            assert upd.shift_id
            models.WorkerShiftComment.objects.filter(
                worker=worker,
                shift_id=upd.shift_id,
            ).delete()

            upd.create_changelog_entry(
                "unregister",
                worker=worker,
            )

        if action in ("registercomment", "savecomment"):
            new_comment = form.cleaned_data["owncomment"]
            assert new_comment is not None
            if shift_id is None:
                shift_id = upd.get_or_create_shift_id()
            if shift_id is None:
                return self.render_to_response(
                    self.get_context_data(**kwargs, form_error="No such shift")
                )
            try:
                ex_comment = models.WorkerShiftComment.objects.get(
                    worker=worker,
                    shift_id=shift_id,
                )
            except models.WorkerShiftComment.DoesNotExist:
                old_comment = ""
                if old_comment != new_comment:
                    models.WorkerShiftComment.objects.create(
                        worker=worker,
                        shift_id=shift_id,
                        comment=form.cleaned_data["owncomment"],
                    )
            else:
                old_comment = ex_comment.comment
                ex_comment_qs = models.WorkerShiftComment.objects.filter(
                    id=ex_comment.id
                )
                if old_comment != new_comment and not new_comment:
                    ex_comment_qs.delete()
                elif old_comment != new_comment:
                    ex_comment_qs.update(comment=new_comment)
            if old_comment != new_comment:
                models.Changelog.create_now(
                    "comment",
                    {
                        "workplace": upd.workplace.slug,
                        "date": str(upd.date),
                        "shift": upd.slug,
                        "old": old_comment,
                        "new": new_comment,
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

        shifts_for_date = {d: [] for d in dates}
        weekdays = [{"date": d, "shifts": shifts_for_date[d]} for d in dates]

        shift_qs = models.Shift.objects.filter(date__in=dates)
        shift_qs = shift_qs.order_by("date", "order")
        shift_id_to_worker_list = {}
        for s in shift_qs.values("id", "date", "name", "slug", "settings"):
            s_id = s.pop("id")
            s_date = s.pop("date")
            s["workers"] = []
            shift_id_to_worker_list[s_id] = s
            shifts_for_date[s_date].append(s)

        ws_qs = models.WorkerShift.objects.filter(
            shift_id__in=shift_id_to_worker_list.keys()
        )
        ws_qs = ws_qs.values_list("shift_id", "worker_id", "worker__name")
        my_id = worker.id if worker else None
        ws_qs = ws_qs.order_by("order")
        for shift_id, worker_id, worker_name in ws_qs:
            me = my_id == worker_id
            shift_id_to_worker_list[shift_id]["workers"].append(
                {"me": me, "name": worker_name}
            )
            if me:
                shift_id_to_worker_list[shift_id]["me"] = True

        wsc_qs = (
            models.WorkerShiftComment.objects.filter(
                worker=worker, shift_id__in=shift_id_to_worker_list.keys()
            )
            if worker
            else models.WorkerShiftComment.objects.none()
        )
        for shift_id, comment in wsc_qs.values_list("shift_id", "comment"):
            shift_id_to_worker_list[shift_id]["own_comment"] = comment

        workplace_settings = json.loads(
            models.Workplace.objects.values_list("settings", flat=True)[:1][0]
        )
        for s_date in shifts_for_date:
            if shifts_for_date[s_date]:
                continue
            for s in models.day_shifts_for_settings(s_date, workplace_settings):
                shifts_for_date[s_date].append(
                    {
                        "name": s.name,
                        "slug": s.slug,
                        "workers": [],
                        "settings": s.settings,
                    }
                )

        if worker:
            now = timezone.now()
            for s in (s for ss in shifts_for_date.values() for s in ss):
                s_settings = json.loads(s.pop("settings"))
                s["open"] = compute_is_registration_open(s_settings, now)
        year, weekno, _ = monday.isocalendar()
        return {
            "message_of_the_day": workplace_settings.get("message_of_the_day"),
            "form_error": kwargs.get("form_error"),
            "worker": worker,
            "next": next_url,
            "prev": prev_url,
            "week": weekno,
            "year": year,
            "weekdays": weekdays,
        }


class WorkerShiftListView(TemplateView):
    template_name = "shifts/worker_shift_list.html"

    def get_worker_admin(self) -> Optional[models.Worker]:
        if not self.request.user.has_perm("shifts.api"):
            return None
        if "wid" not in self.request.GET:
            return None
        try:
            return models.Worker.objects.get(id=self.request.GET["wid"])
        except (ValueError, models.Worker.DoesNotExist):
            raise Http404

    def get_worker_self(self) -> Optional[models.Worker]:
        cookie = self.request.COOKIES.get("shiftplannerlogin", "")
        return models.Worker.get_by_cookie_secret(cookie)

    def get(self, *args, **kwargs):
        self.worker_admin = self.get_worker_admin()
        self.worker = self.worker_admin or self.get_worker_self()
        if not self.worker:
            return HttpResponseRedirect(
                f"/login/?{urllib.parse.urlencode(dict(next=self.request.path))}"
            )
        return super().get(*args, **kwargs)

    def get_context_data(self):
        qs = models.WorkerShift.objects.filter(worker=self.worker)
        qs = qs.values_list("shift__date", "shift__order", "shift__name", "order")
        shifts = []
        for shift_date, shift_order, shift_name, order in qs:
            iso = shift_date.isocalendar()
            shifts.append(
                {
                    "key": (shift_date, shift_order, 0),
                    "link": f"/s/{iso.year}w{iso.week}/",
                    "isoyear": iso.year,
                    "isoweek": iso.week,
                    "date": shift_date,
                    "name": shift_name,
                    "order": order,
                    "comment": None,
                }
            )
        qs_wsc = models.WorkerShiftComment.objects.filter(worker=self.worker)
        qs_wsc = qs_wsc.values_list(
            "shift__date", "shift__order", "shift__name", "comment"
        )
        for shift_date, shift_order, shift_name, comment in qs_wsc:
            iso = shift_date.isocalendar()
            shifts.append(
                {
                    "key": (shift_date, shift_order, 1),
                    "link": f"/s/{iso.year}w{iso.week}/",
                    "isoyear": iso.year,
                    "isoweek": iso.week,
                    "date": shift_date,
                    "name": shift_name,
                    "order": order,
                    "comment": comment,
                }
            )
        shifts.sort(key=lambda o: o["key"])
        return {
            "worker_admin": self.worker_admin,
            "worker": self.worker,
            "shifts": shifts,
        }


class WorkerLoginView(FormView):
    form_class = forms.WorkerLoginForm
    template_name = "shifts/worker_login.html"

    def form_valid(self, form):
        try:
            worker = models.Worker.objects.get(phone=form.cleaned_data["phone"])
        except models.Worker.DoesNotExist:
            form.add_error("phone", "Ingen bruger fundet")
            return self.form_invalid(form)
        if worker.login_secret != form.cleaned_data["password"]:
            form.add_error("password", "Forkert kodeord")
            return self.form_invalid(form)
        if not worker.active:
            form.add_error(
                "phone", "Din bruger er inaktiv - kontakt venligst planlæggeren"
            )
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
        models.Changelog.create_now(
            "worker_login",
            {},
            worker=worker,
        )
        return resp


class WorkerLogoutView(TemplateView):
    template_name = "shifts/worker_logout.html"

    def post(self, request):
        cookie = self.request.COOKIES.get("shiftplannerlogin", "")
        worker = models.Worker.get_by_cookie_secret(cookie)

        resp = HttpResponseRedirect("/")
        resp.delete_cookie(
            "shiftplannerlogin",
            samesite="Strict",
        )
        models.Changelog.create_now(
            "worker_logout",
            {},
            worker=worker,
        )
        return resp


class AdminLoginView(auth_views.LoginView):
    template_name = "shifts/admin_login.html"

    def get_success_url(self):
        return self.get_redirect_url() or "/admin/"


class AdminLogoutView(auth_views.LogoutView):
    next_page = "/"


# ScheduleEdit (admin)
# TodayView (internal)
# WorkerList (admin)
# - Login links to forward to workers


class ApiWorkerList(ApiMixin, View):
    def get(self, request):
        worker_fields = [
            "id",
            "name",
            "phone",
            "login_secret",
            "active",
            "note",
            "email",
        ]
        qs = models.Worker.objects.values(*worker_fields)
        qs = qs.order_by("name")
        workers = list(qs)
        return JsonResponse({"fields": worker_fields, "rows": workers})

    def post(self, request):
        try:
            new = json.loads(request.body.decode("utf-8"))
        except Exception:
            return JsonResponse({"error": "expected JSON body"}, status=400)
        if not isinstance(new, list):
            return JsonResponse({"error": "expected JSON list"}, status=400)
        if not new:
            return JsonResponse({"ok": True, "noop": True})
        new_list = []
        names = []
        phones = []
        emails = []
        for w in new:
            if not isinstance(w, dict):
                return JsonResponse(
                    {"error": "expected JSON list of dicts"}, status=400
                )
            if not w.keys() <= {"name", "phone", "note", "email"}:
                return JsonResponse(
                    {"error": "expected name,phone,note,email"}, status=400
                )
            new_list.append(
                models.Worker(
                    name=w["name"],
                    phone=w["phone"],
                    note=w["note"],
                    email=w["email"],
                    login_secret=models.random_secret(12),
                )
            )
            try:
                new_list[-1].clean()
            except Exception as e:
                return JsonResponse({"error": str(e)}, status=400)
            names.append(w["name"])
            if w["phone"]:
                phones.append(w["phone"])
            if w["email"]:
                emails.append(w["email"])
        if (
            len(names) != len(set(names))
            or len(phones) != len(set(phones))
            or len(emails) != len(set(emails))
        ):
            return JsonResponse(
                {"error": "names and phones and emails must be unique"}, status=400
            )
        qs = (
            models.Worker.objects.filter(name__in=names)
            | models.Worker.objects.filter(phone__in=phones)
            | models.Worker.objects.filter(email__in=emails)
        )
        try:
            ex = qs[:1].get()
        except models.Worker.DoesNotExist:
            pass
        else:
            return JsonResponse(
                {"error": "Already exists: %s/%s/%s" % (ex.name, ex.phone, ex.email)},
                status=400,
            )
        models.Worker.objects.bulk_create(new_list)
        models.Changelog.create_now(
            "import_workers",
            {"names": names},
            user=request.user,
        )
        return JsonResponse({"ok": True, "count": len(new_list)})


class ApiWorker(ApiMixin, View):
    def get(self, request, id):
        worker_fields = [
            "id",
            "name",
            "phone",
            "login_secret",
            "active",
            "note",
            "email",
        ]
        try:
            worker = models.Worker.objects.values(*worker_fields).get(id=id)
        except models.Worker.DoesNotExist:
            raise Http404
        fields = ["order", "shift__date", "shift__order", "shift__slug", "shift__name"]
        shifts = models.WorkerShift.objects.filter(worker_id=worker["id"])
        shifts_list = list(shifts.values(*fields))
        return JsonResponse(
            {"row": worker, "shifts": {"fields": fields, "rows": shifts_list}}
        )

    def post(self, request, id):
        qs = models.Worker.objects.filter(id=id)
        edit_fields = ["name", "phone", "note", "active", "email"]
        try:
            old = qs.values(*edit_fields).get()
        except models.Worker.DoesNotExist:
            raise Http404
        assert not any(v is None for v in old.values()), (id, old)
        try:
            new = json.loads(request.body.decode("utf-8"))
        except Exception:
            return JsonResponse({"error": "expected JSON body"}, status=400)
        bad = [k for k in edit_fields if k in new and type(old[k]) != type(new[k])]
        if bad:
            return JsonResponse(
                {"error": "bad keys/types in JSON", "debug": {"bad": bad}}, status=400
            )
        changed = {k: new[k] for k in edit_fields if k in new and old[k] != new[k]}
        if not changed:
            return JsonResponse({"ok": True, "debug": {"changed": changed}})
        if changed.get("name") == "":
            return JsonResponse({"error": "Navn må ikke være blankt"})
        if changed.get("name"):
            ex = models.Worker.objects.exclude(id=id).filter(name=changed["name"])
            if ex.exists():
                return JsonResponse({"error": "En anden vagttager har dette navn"})
        if changed.get("phone"):
            ex = models.Worker.objects.exclude(id=id).filter(phone=changed["phone"])
            if ex.exists():
                return JsonResponse(
                    {"error": "En anden vagttager har dette telefonnummer"}
                )
        if changed.get("email"):
            ex = models.Worker.objects.exclude(id=id).filter(email=changed["email"])
            if ex.exists():
                return JsonResponse(
                    {"error": "En anden vagttager har denne emailadresse"}
                )
        qs.update(**changed)
        models.Changelog.create_now(
            "edit_worker",
            {
                "id": id,
                "old": old,
                "changed": changed,
            },
            user=request.user,
        )
        return JsonResponse({"ok": True})


class ApiWorkerShiftDataDelete(ApiMixin, View):
    def get(self, request):
        workplace = models.Workplace.objects.all()[:1][0]
        workplace_settings = workplace.get_settings()
        if "retain_weeks" not in workplace_settings:
            return JsonResponse(
                {"error": "Workplace is not configured to use this feature"},
                status=400,
            )
        retain_weeks = workplace_settings["retain_weeks"]
        today = datetime.date.today()
        monday = today - datetime.timedelta(today.weekday())
        before = monday - datetime.timedelta(7 * retain_weeks)
        shifts = models.Shift.objects.filter(workplace=workplace, date__lt=before)
        qs = models.WorkerShift.objects.filter(shift__in=shifts)
        qsc = models.WorkerShiftComment.objects.filter(shift__in=shifts)
        info = {
            "before": before.strftime("%Y-%m-%d"),
            "shifts": qs.count(),
            "comments": qsc.count(),
        }
        dates = {
            *qs.values_list("shift__date", flat=True).distinct(),
            *qsc.values_list("shift__date", flat=True).distinct(),
        }
        if dates:
            min_date = min(dates).isocalendar()
            max_date = max(dates).isocalendar()
            info["earliest"] = "%sw%s" % (min_date.year, min_date.week)
            info["latest"] = "%sw%s" % (max_date.year, max_date.week)
        return JsonResponse(info)

    def post(self, request):
        try:
            req = json.loads(request.body.decode("utf-8"))
        except Exception:
            return JsonResponse({"error": "expected JSON body"}, status=400)
        try:
            assert isinstance(req, dict)
            before_str = req["before"]
            assert isinstance(before_str, str)
            before = datetime.datetime.strptime(before_str, "%Y-%m-%d").date()
            shifts_count = req["shifts"]
            comments_count = req["comments"]
            assert isinstance(shifts_count, int)
            assert isinstance(comments_count, int)
        except (TypeError, KeyError, AssertionError):
            return JsonResponse(
                {
                    "error": 'expected JSON body with object keys "before", "shifts", "comments"'
                },
                status=400,
            )
        workplace = models.Workplace.objects.all()[:1][0]
        shifts = models.Shift.objects.filter(workplace=workplace, date__lt=before)
        qs = models.WorkerShift.objects.filter(shift__in=shifts)
        qsc = models.WorkerShiftComment.objects.filter(shift__in=shifts)
        if qs.count() != shifts_count or qsc.count() != comments_count:
            return JsonResponse(
                {"error": "stale info for counts, please try again"},
                status=400,
            )
        *prep, add_counts = models.prepare_update_worker_shift_aggregate_count()
        models.do_update_worker_shift_aggregate_count(add_counts)
        actual_shifts_count = qs.delete()
        actual_comments_count = qsc.delete()
        debug_data = {
            "prep": prep,
            "shifts": actual_shifts_count,
            "comments": actual_comments_count,
        }
        return JsonResponse({"ok": True, "debug": debug_data})


class ApiWorkerDelete(ApiMixin, View):
    def get(self, request):
        return JsonResponse(
            {"hint": "This API endpoint only supports POST with JSON body"}
        )

    def post(self, request):
        try:
            req = json.loads(request.body.decode("utf-8"))
        except Exception:
            return JsonResponse({"error": "expected JSON body"}, status=400)
        try:
            workers = req["workers"]
            assert isinstance(workers, list)
        except (TypeError, KeyError, AssertionError):
            return JsonResponse(
                {
                    "error": 'expected JSON body with object key "workers" containing a list'
                },
                status=400,
            )
        worker_data = {}
        keys = ("name", "phone", "email", "note", "active")
        try:
            for w in workers:
                w_id = w["id"]
                w_tuple = tuple(w[k] for k in keys)
                ex = worker_data.setdefault(w_id, w_tuple)
                if ex is not w_tuple:
                    return JsonResponse(
                        {"error": "duplicate id %s in workers" % w_id}, status=400
                    )
        except (TypeError, KeyError) as e:
            return JsonResponse(
                {"error": "error while processing JSON body", "debug": repr(e)},
                status=400,
            )
        qs = models.Worker.objects.filter(id__in=worker_data.keys())
        ex_data = list(qs.values_list("id", *keys))
        missing = worker_data.keys() - set(w_id for w_id, *w_tuple in ex_data)
        found_ids = []
        for w_id, *w_data in ex_data:
            assert isinstance(worker_data[w_id], tuple)
            if worker_data[w_id] == tuple(w_data):
                found_ids.append(w_id)
            else:
                return JsonResponse(
                    {
                        "error": "stale info for worker with id %s" % w_id,
                        "debug": {"db": w_tuple, "request": worker_data[w_id]},
                    },
                    status=400,
                )
        *prep, add_counts = models.prepare_update_worker_shift_aggregate_count()
        models.do_update_worker_shift_aggregate_count(add_counts)
        del_count = qs.delete()
        debug_data = {"prep": prep, "del_count": del_count, "missing": sorted(missing)}
        return JsonResponse({"ok": True, "debug": debug_data})


class ApiWorkerStats(ApiMixin, View):
    def get(self, request):
        return JsonResponse({"workers": models.get_worker_stats()})


class ApiWorkplace(ApiMixin, View):
    def get(self, request):
        fields = ["id", "slug", "name", "settings"]
        workplace = models.Workplace.objects.values(*fields).order_by("id")[:1][0]
        workplace["settings"] = json.loads(workplace["settings"])
        return JsonResponse({"rows": [workplace]})

    def post(self, request):
        id, settings_str = models.Workplace.objects.values_list(
            "id", "settings"
        ).order_by("id")[:1][0]
        old_settings = json.loads(settings_str)
        try:
            new = json.loads(request.body.decode("utf-8"))
        except Exception:
            return JsonResponse({"error": "expected JSON body"}, status=400)
        try:
            new_settings = models.validate_workplace_settings(new["settings"])
        except ValueError as e:
            return JsonResponse(
                {"error": "bad settings", "debug": {"e": str(e)}},
                status=400,
            )
        combined = typing.cast(Any, {**old_settings, **new_settings})
        changed = {
            k: combined[k]
            for k in combined
            if k not in old_settings or combined[k] != old_settings[k]
        }
        if not changed:
            return JsonResponse({"ok": True, "debug": {"noop": True}})
        models.Workplace.objects.filter(id=id).update(settings=json.dumps(combined))
        models.Changelog.create_now(
            "edit_workplace_settings",
            {
                "id": id,
                "old": old_settings,
                "changed": changed,
            },
            user=request.user,
        )
        return JsonResponse({"ok": True})


class WeekFilterMixin:
    def get_week_filter(
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
                ).date()
            except ValueError:
                raise ValueError("bad fromdate")
        if "untildate" in self.request.GET:
            try:
                untildate = datetime.datetime.strptime(
                    self.request.GET["untildate"], "%Y-%m-%d"
                ).date()
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


class ApiShiftList(ApiMixin, View, WeekFilterMixin):
    def add_default_shifts(
        self,
        shifts_db: List[Any],
        fromdate: Optional[datetime.date],
        untildate: Optional[datetime.date],
    ) -> None:
        assert fromdate is None or isinstance(fromdate, datetime.date)
        assert untildate is None or isinstance(untildate, datetime.date)
        workplace_settings = json.loads(
            models.Workplace.objects.values_list("settings", flat=True)[:1][0]
        )
        seen_dates: Set[datetime.date] = set(row["date"] for row in shifts_db)
        if fromdate is None:
            if not seen_dates:
                return
            fromdate = min(seen_dates)
            fromdate -= datetime.timedelta(untildate.weekday())
        if untildate is None:
            if not seen_dates:
                return
            untildate = max(seen_dates)
            untildate += datetime.timedelta(6 - untildate.weekday())
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
            fromdate, untildate, monday = self.get_week_filter()
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
        wsc_qs = models.WorkerShiftComment.objects.filter(shift__in=qs)
        wsc_db = wsc_qs.values_list("shift_id", "worker_id", "comment")
        wsc_db = wsc_db.order_by("shift_id")
        shifts_db = list(qs.values("id", "date", "order", "slug", "name", "settings"))
        self.add_default_shifts(shifts_db, fromdate, untildate)
        shifts_db.sort(key=lambda s: (s["date"], s["order"]))
        shifts_json = [
            {
                **row,
                "date": row["date"].strftime("%Y-%m-%d"),
                "settings": json.loads(row["settings"]),
                "workers": [],
                "comments": [],
            }
            for row in shifts_db
        ]
        shifts_by_id = {s["id"]: s for s in shifts_json if s["id"] is not None}
        for shift_id, order, worker_id, worker_name in workers_db:
            shifts_by_id[shift_id]["workers"].append(
                {"id": worker_id, "name": worker_name}
            )
        for shift_id, worker_id, comment in wsc_db:
            shifts_by_id[shift_id]["comments"].append(
                {"id": worker_id, "comment": comment}
            )
        result: Dict[str, Any] = {"rows": shifts_json}
        if monday is not None:
            prev_monday = (monday - datetime.timedelta(7)).isocalendar()
            result["prev"] = f"{prev_monday.year}w{prev_monday.week}"
            next_monday = (monday + datetime.timedelta(7)).isocalendar()
            result["next"] = f"{next_monday.year}w{next_monday.week}"
        return JsonResponse(result)

    def post(self, request):
        workplace = models.Workplace.objects.all()[:1][0]
        try:
            data = json.loads(request.body.decode("utf-8"))
        except Exception:
            return JsonResponse({"error": "expected JSON body"}, status=400)
        materialize = [
            datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            for date_str in data.get("materializeDays") or []
        ]
        if materialize:
            materialize = sorted(
                set(materialize)
                - set(
                    models.Shift.objects.filter(
                        workplace=workplace,
                        date__in=sorted(set(materialize)),
                    )
                    .values_list("date", flat=True)
                    .distinct()
                )
            )
        new_shifts = []
        if materialize:
            workplace_settings = workplace.get_settings()
            for date in materialize:
                new_shifts += models.day_shifts_for_settings(
                    date, workplace_settings, workplace
                )
            for s in new_shifts:
                s.save()
        delete = []
        update = []
        update_reorder = []
        insert = []
        for date_str, shifts in (data.get("modifiedDays") or {}).items():
            date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            ex = list(
                models.Shift.objects.filter(
                    workplace=workplace,
                    date=date,
                ).order_by("order")
            )
            settings = ex[0].settings if ex else "{}"
            dupe_order = len(set(e.order for e in ex)) != len(ex)
            ex_ids = [e.id for e in ex]
            new_ids = [e.get("id") for e in shifts]
            new_ids_set = set(new_ids)
            for e in ex:
                if e.id not in new_ids_set:
                    delete.append(e.id)
            if dupe_order or ex_ids != new_ids:
                for i, s in enumerate(shifts, 1):
                    s_id = s.get("id")
                    if s_id is None:
                        insert.append((date, i, s["name"], settings))
                    else:
                        update_reorder.append((s_id, i, s["name"]))
            else:
                for s in enumerate(shifts, 1):
                    s_id = s.get("id")
                    assert s_id is not None
                    update.append((s_id, s["name"]))
        delete = sorted(
            set(delete)
            - set(
                models.WorkerShift.objects.filter(shift_id__in=delete)
                .values_list("shift_id", flat=True)
                .distinct()
            )
        )
        if delete:
            models.Shift.objects.filter(id__in=delete).delete()
        for date, order, name, settings in insert:
            models.Shift.objects.create(
                workplace=workplace,
                date=date,
                order=order,
                slug=name,
                name=name,
                settings=settings,
            )
        for id, order, name in update_reorder:
            models.Shift.objects.filter(id=id).update(name=name, slug=name, order=order)
        for id, name in update:
            models.Shift.objects.filter(id=id).update(name=name, slug=name)
        return JsonResponse(
            {
                "ok": True,
                "debug": {
                    "insert": insert,
                    "update": update,
                    "update_reorder": update_reorder,
                    "delete": delete,
                    "new_shifts": len(new_shifts),
                },
            },
            status=200,
        )


class ApiShift(ApiMixin, View):
    def post(self, request, **kwargs):
        date_str: str = kwargs["date"]
        slug: str = kwargs["slug"]
        try:
            date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            raise Http404
        workplace = models.Workplace.objects.all()[:1][0]
        upd = prepare_shift_update(workplace, date, slug)
        shift_id = upd.get_or_create_shift_id()
        if shift_id is None:
            raise Http404
        try:
            data = json.loads(request.body.decode("utf-8"))
        except Exception:
            return JsonResponse({"error": "expected JSON body"}, status=400)
        workers = data["workers"]
        worker_ids = set(w["id"] for w in workers)
        if len(worker_ids) != len(workers):
            return JsonResponse(
                {"error": "worker IDs in shift must be distinct"}, status=400
            )
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


class ApiChangelog(ApiMixin, View, WeekFilterMixin):
    def get(self, request):
        qs = models.Changelog.objects.all()
        try:
            fromdate, untildate, monday = self.get_week_filter()
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=400)
        if fromdate is not None:
            qs = qs.filter(
                time__gte=datetime.datetime.combine(fromdate, datetime.time())
            )
        if untildate is not None:
            qs = qs.filter(
                time__lte=datetime.datetime.combine(untildate, datetime.time())
            )
        worker_id = self.request.GET.get("worker")
        if worker_id is not None:
            qs = qs.filter(worker_id=worker_id)
        qs = qs.order_by("time")
        try:
            limit = int(self.request.GET["limit"])
        except KeyError:
            limit = 1000
        except ValueError:
            return JsonResponse({"error": "bad limit"}, status=400)
        qs = qs[:limit].values("time", "worker_id", "user_id", "kind", "data")
        changelog_json = [
            {
                **row,
                "time": row["time"].timestamp(),
                "data": json.loads(row["data"]) if row["data"] else {},
            }
            for row in qs
        ]
        return JsonResponse({"rows": changelog_json})


def get_workers_by_id() -> Dict[int, Any]:
    worker_by_id = {}
    for worker in models.Worker.objects.all():
        w = worker_by_id[worker.id] = {"name": worker.name}
        if worker.phone:
            w["phone"] = worker.phone
        if worker.login_secret:
            w["login_secret"] = worker.login_secret
        if worker.cookie_secret:
            w["cookie_secret"] = worker.cookie_secret
        if worker.email:
            w["email"] = worker.email
    return worker_by_id


def get_workplaces_by_id() -> Dict[int, Any]:
    workplace_by_id = {}
    for workplace in models.Workplace.objects.all():
        workplace_by_id[workplace.id] = {
            "name": workplace.name,
            "slug": workplace.slug,
            **workplace.get_settings(),
            "shifts": [],
        }
    return workplace_by_id


def id_map_to_name_map(
    d: Dict[int, Any], k: str
) -> Tuple[Dict[int, str], Dict[str, Any]]:

    name_to_id: Dict[str, int] = {}
    id_to_name: Dict[int, str] = {}
    res: Dict[str, Any] = {}
    for i, w in d.items():
        if w[k] in name_to_id:
            n = next(
                n
                for n in ("%s%s" % (w[k], i) for i in range(1000))
                if n not in name_to_id
            )
        else:
            n = w.pop(k)
        name_to_id[n] = i
        id_to_name[i] = n
        res[n] = w
    return id_to_name, res


class ApiExport(ApiMixin, View):
    def get(self, request):
        worker_id_to_name, workers = id_map_to_name_map(get_workers_by_id(), "name")
        workplace_id_to_name, workplaces = id_map_to_name_map(
            get_workplaces_by_id(), "name"
        )

        shift_id_to_worker_list: Dict[int, List[Any]] = {}
        for shift in models.Shift.objects.order_by("date", "order"):
            sh = shift.as_dict()
            workplaces[workplace_id_to_name[shift.workplace_id]]["shifts"].append(sh)
            sh["workers"] = shift_id_to_worker_list[shift.id] = []
        for ws in models.WorkerShift.objects.order_by("order"):
            shift_id_to_worker_list[ws.shift_id].append(worker_id_to_name[ws.worker_id])
        return JsonResponse(
            {
                "workers": workers,
                "workplaces": workplaces,
            }
        )


class AdminPrintView(ApiMixin, TemplateView):
    template_name = "shifts/schedule_print.html"

    def get_context_data(self, **kwargs):
        workplace = models.Workplace.objects.all()[:1][0]
        workplace_settings = workplace.get_settings()
        print_header_text = workplace_settings.get("print_header_text") or ""
        max_print = int(workplace_settings.get("max_print_per_shift") or 3)
        monday = monday_from_week_string(self.kwargs["week"])
        if monday is None:
            raise Http404
        dates = [monday + datetime.timedelta(d) for d in range(7)]
        shift_qs = models.Shift.objects.filter(date__in=dates)
        wsc_qs = models.WorkerShiftComment.objects.filter(shift__in=shift_qs)
        wsc = {
            (w, s): c
            for w, s, c in wsc_qs.values_list("worker_id", "shift_id", "comment")
        }
        ws_qs = models.WorkerShift.objects.filter(shift__in=shift_qs)
        ws_qs = ws_qs.order_by("shift__date", "shift__order", "order")
        ws_qs = ws_qs.values(
            "worker_id",
            "shift_id",
            "shift__date",
            "worker__name",
            "worker__phone",
            "worker__email",
            "shift__slug",
            "worker__note",
        )
        rows = []
        groups = itertools.groupby(
            ws_qs, key=lambda row: (row["shift__date"], row["shift__slug"])
        )
        for _, g in groups:
            for row in list(g)[:max_print]:
                worker_comment = wsc.get((row["worker_id"], row["shift_id"]))
                phone = row["worker__phone"]
                if len(phone) == 8:
                    phone = "%s %s" % (phone[:4], phone[4:])
                email = row["worker__email"]
                rows.append(
                    (
                        row["shift__date"],
                        row["worker__name"],
                        phone,
                        email,
                        row["shift__slug"],
                        row["worker__note"],
                        worker_comment,
                    )
                )
        isocal = monday.isocalendar()
        return {
            "year": isocal.year,
            "week": isocal.week,
            "rows": rows,
            "print_header_text": print_header_text,
        }


class AdminViewBase(ApiMixin, TemplateView):
    template_name = "shifts/admin.html"

    title: str
    styles: List[str] = []
    container_class = ""

    def get_options(self):
        try:
            return getattr(self, "options")
        except AttributeError:
            return {}

    def get_context_data(self, **kwargs):
        workplace = models.Workplace.objects.all()[:1][0]
        if settings.FRONTEND_DEV_MODE:
            port = settings.FRONTEND_DEV_PORT
            styles = [static(s) for s in self.styles]
            scripts = [f"http://localhost:{port}/src/index.tsx"]
        else:
            manifest = json.loads(settings.FRONTEND_MANIFEST)
            files = [
                manifest["index.html"],
                *manifest["index.html"].get("imports", {}).values(),
            ]
            styles = [
                static(s)
                for styles in [self.styles, *(f.get("css", []) for f in files)]
                for s in styles
            ]
            scripts = [static(s["file"]) for s in files]
        return {
            "options_json": SafeString(json.dumps(self.get_options())),
            "workplace_json": SafeString(json.dumps(workplace.get_settings())),
            "title": self.title,
            "styles": styles,
            "scripts": scripts,
            "FRONTEND_DEV_MODE": settings.FRONTEND_DEV_MODE,
            "container_class": self.container_class,
        }


class AdminScheduleView(AdminViewBase):
    title = "Vagtbooking"
    styles = ["shifts/schedule.css"]
    container_class = "sp_schedule"

    def get_options(self):
        monday = monday_from_week_string(self.kwargs["week"])
        if monday is None:
            raise Http404
        isocal = monday.isocalendar()
        return {
            "view": "schedule",
            "year": isocal.year,
            "week": isocal.week,
        }


class AdminWorkersView(AdminViewBase):
    title = "Vagttagere"
    styles = ["shifts/admin_workers.css"]
    container_class = "sp_workers"
    options = {"view": "workers"}


class AdminShiftsView(AdminViewBase):
    title = "Vagter"
    styles = []
    options = {"view": "shifts"}


class AdminChangelogView(AdminViewBase):
    title = "Ændringer"
    styles = []
    options = {"view": "changelog"}


class AdminSettingsView(AdminViewBase):
    title = "Indstillinger"
    styles = ["shifts/admin_settings.css"]
    options = {"view": "settings"}


class AdminWorkerStatsView(AdminViewBase):
    title = "Statistik over vagttagere"
    styles = ["shifts/admin_worker_stats.css"]
    options = {"view": "workerStats"}


def silent_page_not_found(request):
    response = HttpResponseNotFound("<h1>Not Found</h1>")
    response._has_been_logged = True
    return response
