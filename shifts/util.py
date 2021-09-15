import datetime


def get_isocalender(year: int, week: int, weekday: int) -> datetime.date:
    """
    >>> get_isocalender(2021, 52, 6)
    datetime.date(2022, 1, 2)
    >>> get_isocalender(2022, 1, 0)
    datetime.date(2022, 1, 3)
    >>> get_isocalender(2022, 52, 0)
    datetime.date(2022, 12, 26)
    >>> get_isocalender(2022, 52, 6)
    datetime.date(2023, 1, 1)
    >>> get_isocalender(2022, 42, 3)
    datetime.date(2022, 10, 20)
    """
    d = datetime.date(year, 2, 1)
    d += datetime.timedelta(weekday - d.weekday())
    while True:
        i = d.isocalendar()
        assert i.weekday - 1 == weekday, (i.weekday, weekday)
        if (i.year, i.week) == (year, week):
            return d
        if i.year == year:
            d += datetime.timedelta(7 * (week - i.week))
            i = d.isocalendar()
            if (i.year, i.week) != (year, week):
                assert not 1 <= week <= 52
                raise ValueError("bad week: %s-%s" % (year, week))
            return d
        d += datetime.timedelta(7 * (year - i.year))
