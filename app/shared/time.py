from datetime import datetime
from zoneinfo import ZoneInfo

SEOUL = ZoneInfo("Asia/Seoul")


def as_seoul_time(value: datetime) -> datetime:
    """Interpret a form datetime as Asia/Seoul, or convert an aware value to it."""
    return value.replace(tzinfo=SEOUL) if value.tzinfo is None else value.astimezone(SEOUL)
