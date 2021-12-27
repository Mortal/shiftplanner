from django.test import TestCase

from shifts import models


class WorkerStatsTestCase(TestCase):
    def setUp(self):
        from importexport import create_shifts

        create_shifts()

    def test(self):
        s1 = models.get_current_worker_stats()
        s2 = models.get_worker_stats()
        self.assertEqual(s1, s2)
        (
            stat_pos,
            stat_nul,
            stat_neg,
            add_counts,
        ) = models.prepare_update_worker_shift_aggregate_count()
        self.assertNotEqual(0, stat_pos)
        self.assertEqual(0, stat_nul)
        self.assertEqual(0, stat_neg)
        self.assertEqual(stat_pos + stat_neg, len(add_counts))
        for k, row_id, count in add_counts:
            worker, isoyearweek, yearmonth = k
            if row_id is not None:
                qs = models.WorkerShiftAggregateCount.objects.filter(id=row_id)
                assert qs.values_list(
                    "worker_id", "isoyearweek", "yearmonth"
                ).get() == (worker, isoyearweek, yearmonth)
        models.do_update_worker_shift_aggregate_count(add_counts)

        s1 = models.get_current_worker_stats()
        s2 = models.get_worker_stats()
        self.assertEqual(s1, s2)
        (
            stat_pos,
            stat_nul,
            stat_neg,
            add_counts,
        ) = models.prepare_update_worker_shift_aggregate_count()
        self.assertEqual(0, stat_pos)
        self.assertNotEqual(0, stat_nul)
        self.assertEqual(0, stat_neg)
        self.assertEqual(stat_pos + stat_neg, len(add_counts))
