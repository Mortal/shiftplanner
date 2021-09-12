# From https://github.com/pixeldomain/django-datetime-utc/blob/master/datetimeutc/fields.py
# This file (django_datetime_utc.py) is Copyright (c) 2016 Darren O'Neill
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import datetime

from django.conf import settings
from django.db import models
from django.utils import timezone


class DateTimeUTCField(models.DateTimeField):
    """Creates a DB timestamp field that is TZ naive."""

    description = "Date (with time and no time zone)"

    def __init__(self, *args, **kwargs):
        super(DateTimeUTCField, self).__init__(*args, **kwargs)

    def db_type(self, connection):
        if connection.settings_dict["ENGINE"] == "django.db.backends.mysql":
            return "datetime"
        else:
            return "timestamp"

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        if isinstance(value, datetime.datetime):
            if settings.USE_TZ and timezone.is_naive(value):
                return value.replace(tzinfo=timezone.utc)
            return value
        return super(DateTimeUTCField, self).to_python(value)

    def get_prep_value(self, value):
        if isinstance(value, datetime.datetime):
            return value.astimezone(timezone.utc)
        return value
