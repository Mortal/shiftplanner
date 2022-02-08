from . import models


def workplace(request):
    try:
        workplace = models.Workplace.objects.all()[:1][0]
    except Exception:
        return {}
    return {"WORKPLACE": workplace.get_settings()}
