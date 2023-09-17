"""
Utils
"""

from datetime import datetime
from dateutil import parser, tz
from pytz import utc


def timeago(date: datetime) -> str:
    """
    Time ago
    """
    diff = datetime.now(tz=tz.tzutc()) - date
    seconds = int(diff.total_seconds())
    ago = "ago"
    if seconds < 0:
        ago = "in the future"
        seconds = abs(seconds)
    if seconds < 60:
        return f"{seconds} second{'s' if seconds != 1 else ''} {ago}"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} {ago}"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} {ago}"
    days = hours // 24
    if days < 30:
        return f"{days} day{'s' if days != 1 else ''} {ago}"
    months = days // 30
    if months < 12:
        return f"{months} month{'s' if months != 1 else ''} {ago}"
    years = months // 12
    return f"{years} year{'s' if years != 1 else ''} {ago}"


def dateit(date: datetime, time_format: str = "%a %b %d %H:%M:%S %Z %Y") -> str:
    """
    Return date in desired format
    """
    if time_format == "timeago":
        return timeago(date.astimezone(tz=tz.tzutc()))
    return date.astimezone().strftime(time_format)


def utc_date(date: str | datetime) -> datetime:
    """
    return UTC normalized datetime object from date
    """
    if isinstance(date, str):
        date = parser.parse(date)
    if date.tzinfo is None:
        date = date.astimezone()
    return utc.normalize(date)
