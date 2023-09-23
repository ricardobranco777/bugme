# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring,invalid-name,no-member

from datetime import datetime
from dateutil import tz
from pytz import utc
from freezegun import freeze_time

from utils import dateit, timeago


# Test cases for the dateit function
def test_dateit():
    # Test date formatting with the default format
    dt = datetime(2023, 9, 10, 15, 30, 0, tzinfo=utc)
    formatted_date = dateit(dt)
    assert formatted_date == "Sun Sep 10 17:30:00 CEST 2023"

    # Test date formatting with a custom format
    custom_format = "%Y-%m-%d %H:%M:%S"
    formatted_date = dateit(dt, time_format=custom_format)
    assert formatted_date == "2023-09-10 17:30:00"

    # Test date formatting with a different custom format
    another_format = "%A, %d %B %Y"
    formatted_date = dateit(dt, time_format=another_format)
    assert formatted_date == "Sunday, 10 September 2023"


# Test case for a date in the future (should return "in the future")
@freeze_time("2023-09-12 12:00:00 UTC")
def test_timeago_future_date():
    date = datetime(2024, 9, 12, 10, 30, 0, tzinfo=tz.tzutc())
    result = timeago(date)
    assert result == "1 year in the future"


# Test case for a date 1 year ago (should return "1 year ago")
@freeze_time("2023-09-12 12:00:00 UTC")
def test_timeago_one_year_ago():
    date = datetime(2022, 9, 12, 10, 30, 0, tzinfo=tz.tzutc())
    result = timeago(date)
    assert result == "1 year ago"


# Test case for a date 1 month ago (should return "1 month ago")
@freeze_time("2023-09-12 12:00:00 UTC")
def test_timeago_one_month_ago():
    date = datetime(2023, 7, 12, 10, 30, 0, tzinfo=tz.tzutc())
    result = timeago(date)
    assert result == "2 months ago"


# Test case for a date 1 day ago (should return "1 day ago")
@freeze_time("2023-09-12 12:00:00 UTC")
def test_timeago_one_day_ago():
    date = datetime(2023, 9, 11, 10, 30, 0, tzinfo=tz.tzutc())
    result = timeago(date)
    assert result == "1 day ago"


# Test case for a date 1 hour ago (should return "1 hour ago")
@freeze_time("2023-09-12 12:00:00 UTC")
def test_timeago_one_hour_ago():
    date = datetime(2023, 9, 12, 10, 30, 0, tzinfo=tz.tzutc())
    result = timeago(date)
    assert result == "1 hour ago"


# Test case for a date 30 seconds ago (should return "30 seconds ago")
@freeze_time("2023-09-12 12:00:30 UTC")
def test_timeago_30_seconds_ago():
    date = datetime(2023, 9, 12, 12, 0, 0, tzinfo=tz.tzutc())
    result = timeago(date)
    assert result == "30 seconds ago"


# Test case for the current date (should return "in the future")
@freeze_time("2023-09-12 12:00:00 UTC")
def test_timeago_current_date():
    date = datetime(2023, 9, 12, 12, 0, 0, tzinfo=tz.tzutc())
    result = timeago(date)
    assert result == "0 seconds ago"
