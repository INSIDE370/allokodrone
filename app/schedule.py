import json
from datetime import datetime, timedelta, tzinfo


def _last_sunday(year, month):
    if month == 12:
        first_next = datetime(year + 1, 1, 1)
    else:
        first_next = datetime(year, month + 1, 1)
    last = first_next - timedelta(days=1)
    return last - timedelta(days=(last.weekday() + 1) % 7)


def _local_is_dst(wall):
    start = _last_sunday(wall.year, 3).replace(hour=2)
    end = _last_sunday(wall.year, 10).replace(hour=3)
    return start <= wall.replace(tzinfo=None) < end


def _utc_is_dst(utc):
    start = _last_sunday(utc.year, 3).replace(hour=1)
    end = _last_sunday(utc.year, 10).replace(hour=1)
    return start <= utc.replace(tzinfo=None) < end


class ParisTime(tzinfo):
    """Heure legale de Paris, sans dependance tzdata (absente sur cette installation Windows)."""

    def utcoffset(self, dt):
        if dt is None:
            return timedelta(hours=1)
        return timedelta(hours=2 if _local_is_dst(dt) else 1)

    def dst(self, dt):
        if dt is None or not _local_is_dst(dt):
            return timedelta(0)
        return timedelta(hours=1)

    def tzname(self, dt):
        return "CEST" if dt is not None and _local_is_dst(dt) else "CET"

    def fromutc(self, dt):
        if dt.tzinfo is not self:
            raise ValueError("fromutc attend l'heure de Paris")
        utc = dt.replace(tzinfo=None)
        offset = timedelta(hours=2 if _utc_is_dst(utc) else 1)
        return (utc + offset).replace(tzinfo=self)


PARIS = ParisTime()

DEFAULT_HOURS = {
    "mon_sat": ["11:30", "22:30"],
    "sun": ["17:00", "22:30"],
}

DEFAULT_MIDI = {
    "start": "12:00",
    "end": "15:00",
    "sunday": False,
}


def now_paris(clock=None):
    if clock is not None:
        if clock.tzinfo is None:
            return clock.replace(tzinfo=PARIS)
        return clock.astimezone(PARIS)
    return datetime.now(PARIS)


def minutes(value):
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def load_json_setting(conn, key, default):
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if not row or row["value"] is None or row["value"] == "":
        return default
    try:
        return json.loads(row["value"])
    except json.JSONDecodeError:
        return row["value"]


def is_open(moment, hours):
    window = hours["sun"] if moment.weekday() == 6 else hours["mon_sat"]
    current = moment.hour * 60 + moment.minute
    return minutes(window[0]) <= current < minutes(window[1])


def is_midi(moment, midi):
    if moment.weekday() == 6 and not midi.get("sunday"):
        return False
    current = moment.hour * 60 + moment.minute
    return minutes(midi["start"]) <= current < minutes(midi["end"])


def slot_inside_hours(slot_date, start_time, end_time, hours):
    start = minutes(start_time)
    end = minutes(end_time)
    if end <= start:
        return False
    day = datetime.fromisoformat(slot_date).weekday()
    window = hours["sun"] if day == 6 else hours["mon_sat"]
    return minutes(window[0]) <= start and end <= minutes(window[1])


def hours_label(hours):
    return (
        f"Lundi \u2013 samedi \u00b7 {hours['mon_sat'][0].replace(':', 'h')} \u2013 {hours['mon_sat'][1].replace(':', 'h')}"
        f" · Dimanche \u00b7 {hours['sun'][0].replace(':', 'h')} \u2013 {hours['sun'][1].replace(':', 'h')}"
    )
