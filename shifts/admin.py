from django.contrib import admin

from . import models

admin.site.register(models.Workplace)
admin.site.register(models.Worker)
admin.site.register(models.Shift)
admin.site.register(models.WorkerShift)
admin.site.register(models.Changelog)
