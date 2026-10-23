"""Parse the edition's English date phrases into date intervals.

The edition writes dates as prose ("on or about Friday, 2 March 1888",
"between about Thursday, 5 and about Thursday, 26 February 1885",
"second half of 1881"). We turn each phrase into an inclusive interval
[earliest, latest] plus flags, and verify any stated weekday against the
calendar so a parsing mistake can't slip through silently.
"""

import calendar
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

MONTHS = {name: i for i, name in enumerate(calendar.month_name) if name}
WEEKDAYS = {name: i for i, name in enumerate(calendar.day_name)}

TOKEN_RE = re.compile(
    r"(?P<wd>(?:Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day)"
    r"|(?P<mon>" + "|".join(MONTHS) + r")"
    r"|(?P<year>18\d\d)"
    r"|(?P<day>\d{1,2})"
    r"|(?P<word>second half of|beginning of|end of|on or about|or about|between|probably"
    r"|about|after|early|late|mid|and|or)"
    r"|(?P<dash>-)"
)

# Parts of a month covered by a vague modifier, as (first day, last day or None for month end).
MONTH_PARTS = {
    "beginning of": (1, 10),
    "early": (1, 10),
    "mid": (11, 20),
    "late": (21, None),
    "end of": (21, None),
    "second half of": (16, None),
}


class DateParseError(ValueError):
    pass


@dataclass
class _Point:
    day: int | None = None
    month: int | None = None
    year: int | None = None
    weekday: int | None = None
    modifier: str | None = None

    def is_empty(self):
        return self.day is None and self.month is None and self.year is None

    def interval(self):
        if self.year is None:
            raise DateParseError("point without a year")
        if self.month is None:
            if self.modifier == "second half of":
                return date(self.year, 7, 1), date(self.year, 12, 31)
            return date(self.year, 1, 1), date(self.year, 12, 31)
        last = calendar.monthrange(self.year, self.month)[1]
        if self.day is not None:
            d = date(self.year, self.month, self.day)
            return d, d
        if self.modifier in MONTH_PARTS:
            lo, hi = MONTH_PARTS[self.modifier]
            return date(self.year, self.month, lo), date(self.year, self.month, hi or last)
        return date(self.year, self.month, 1), date(self.year, self.month, last)


@dataclass
class ParsedDate:
    text: str
    earliest: str
    latest: str | None  # None when open-ended ("after ...")
    approximate: bool  # "about", "on or about"
    probable: bool  # "probably"
    weekday_mismatches: list = field(default_factory=list)

    @property
    def precision(self):
        if self.latest is None:
            return "open"
        if self.earliest == self.latest:
            return "day"
        return "range"


def _normalize(text):
    s = text.strip().rstrip(".")
    s = re.sub(r"^[A-Z][\w\s-]*?,\s+(?=(on or about|between|about)\b)", "", s)  # leading place name
    s = re.sub(r"(\d)([A-Z])", r"\1 \2", s)  # "17June"
    return s


def parse_date(text):
    s = _normalize(text)
    approximate = probable = after = False
    points = [_Point()]
    pending_modifier = None

    pos = 0
    for m in TOKEN_RE.finditer(s):
        gap = s[pos:m.start()]
        if gap.strip(" ,"):
            raise DateParseError(f"unrecognized text {gap.strip()!r} in {text!r}")
        pos = m.end()
        kind, value = m.lastgroup, m.group()
        cur = points[-1]
        if kind == "word":
            if value in ("on or about", "or about", "about"):
                approximate = True
            elif value == "probably":
                probable = True
            elif value == "after":
                after = True
            elif value in MONTH_PARTS:
                pending_modifier = value
            elif value in ("and", "or"):
                if not cur.is_empty():
                    points.append(_Point())
            # "between" carries no information of its own
        elif kind == "dash":
            if not cur.is_empty():
                points.append(_Point())
        elif kind == "wd":
            if cur.day is not None or cur.month is not None:
                cur = _Point()
                points.append(cur)
            cur.weekday = WEEKDAYS[value]
        elif kind == "day":
            if cur.day is not None:
                cur = _Point()
                points.append(cur)
            cur.day = int(value)
        elif kind == "mon":
            if cur.month is not None:
                cur = _Point()
                points.append(cur)
            cur.month = MONTHS[value]
            if pending_modifier:
                cur.modifier, pending_modifier = pending_modifier, None
        elif kind == "year":
            if cur.year is not None:
                cur = _Point()
                points.append(cur)
            cur.year = int(value)
            if pending_modifier and cur.month is None:
                cur.modifier, pending_modifier = pending_modifier, None
    if s[pos:].strip(" ,"):
        raise DateParseError(f"unrecognized text {s[pos:].strip()!r} in {text!r}")

    points = [p for p in points if not p.is_empty()]
    if not points:
        raise DateParseError(f"no date found in {text!r}")

    # Earlier points borrow missing month/year from later ones:
    # "Tuesday, 21 or Wednesday, 22 August 1888".
    for i in range(len(points) - 2, -1, -1):
        p, nxt = points[i], points[i + 1]
        if p.year is None:
            p.year = nxt.year
            if p.month is None and p.day is not None:
                p.month = nxt.month
            # A range that crosses New Year: "between 28 December and 3 January 1882".
            if p.month and nxt.month and p.month > nxt.month:
                p.year -= 1

    intervals = [p.interval() for p in points]
    earliest = min(lo for lo, _ in intervals)
    latest = None if after else max(hi for _, hi in intervals)
    if after:
        earliest += timedelta(days=1)

    mismatches = [
        (date(p.year, p.month, p.day).isoformat(), calendar.day_name[p.weekday])
        for p in points
        if p.weekday is not None and p.day is not None
        and date(p.year, p.month, p.day).weekday() != p.weekday
    ]
    return ParsedDate(
        text=text,
        earliest=earliest.isoformat(),
        latest=latest.isoformat() if latest else None,
        approximate=approximate,
        probable=probable,
        weekday_mismatches=mismatches,
    )
