import datetime

from shifts import models


def prepare_prune_worker_shift(before):
    d = (datetime.date.today() - before).days
    assert d >= 7
    beforeisoyear, beforeisoweek, beforeweekday = before.isocalendar()
    assert beforeweekday == 0
    beforeisoyearweek = 100 * beforeisoyear + beforeisoweek
    (
        stat_pos,
        stat_nul,
        stat_neg,
        add_counts,
    ) = models.prepare_update_worker_shift_aggregate_count()
    for (worker, isoyearweek, yearmonth), rowid, count in add_counts:
        if isoyearweek < beforeisoyearweek:
            raise Exception(
                "Going to prune everything before week %s but there is a pending update for week %s"
                % (beforeisoyearweek, isoyearweek)
            )
    return models.WorkerShift.objects.filter(shift__date__lt=before)
