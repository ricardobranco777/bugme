"""
Utils
"""

from datetime import datetime
from dateutil import parser
from pytz import utc


def html_tag(tag: str, content: str = "", **kwargs) -> str:
    """
    HTML tag
    """
    attributes = " ".join(
        f'{key}="{value}"' for key, value in kwargs.items() if value is not None
    )
    if attributes:
        return f"<{tag} {attributes}>{content}</{tag}>"
    return f"<{tag}>{content}</{tag}>"


def timeago(date: datetime) -> str:
    """
    Time ago
    """
    diff = datetime.now(tz=utc) - date
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
    if date == datetime.max.replace(tzinfo=utc):
        return "not yet"
    date = date.astimezone()
    if time_format == "timeago":
        return timeago(date)
    return date.strftime(time_format)


def utc_date(date: str | datetime | None) -> datetime:
    """
    Return UTC normalized datetime object from date
    """
    if date is None:
        return datetime.max.replace(tzinfo=utc)
    if "DateTime" in str(date.__class__):  # xmlrpc DateTime object
        date = datetime.strptime(str(date), '%Y%m%dT%H:%M:%S')
        date = date.isoformat() + "Z"
    if isinstance(date, str):
        if date.isdigit():
            date = datetime.fromtimestamp(int(date))
        else:
            date = parser.parse(date)
    if date.tzinfo is not None:
        date = date.astimezone(utc)
    else:
        date = date.replace(tzinfo=utc)
    return date
