"""Progress lives in progress/progress.json. It is committed, so GitHub shows the journey."""
import json
from datetime import date, timedelta

from .content import ROOT

PROGRESS = ROOT / "progress" / "progress.json"
LOG = ROOT / "progress" / "LOG.md"
LOG_HEADER = "# Coding log\n\nOne line for every piece of Python I wrote. Appended by `quest.py`.\n\n"
JOURNEY = 40
WEEKLY_TARGET = 5
UNIT_FLAGS = ("lecture", "examples", "pset_attempted", "pset_done", "sidequest", "mastery")


def today():
    return date.today().isoformat()


def fresh():
    return {
        "onboarded": False,
        "units": {},             # unit id -> the UNIT_FLAGS
        "sidequests": {},        # sidequest id -> status, file, hints, checks...
        "recall": {},            # "unit/prompt" -> last rating, due date or retired
        "sessions": {},          # date -> {"unit", "evidence": [...]}; at most one per day
        "builds": [],            # real things built instead of a sidequest
        "independence": 0,       # +1 per no-hint sidequest, -1 per hinted one; drives scaffolding
        "today": {},
        "app_seconds": {},       # date -> seconds spent inside this app
        "maintenance_visits": 0,
    }


def load():
    s = fresh()
    if PROGRESS.exists():
        s.update(json.loads(PROGRESS.read_text(encoding="utf-8")))
    return s


def save(s):
    out = {**s, "app_seconds": {d: round(v) for d, v in s["app_seconds"].items()}}
    PROGRESS.parent.mkdir(exist_ok=True)
    tmp = PROGRESS.with_suffix(".tmp")
    tmp.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    tmp.replace(PROGRESS)


def day(s):
    """Today's scratch record. Resets itself when the date changes."""
    if s["today"].get("date") != today():
        s["today"] = {"date": today()}
    return s["today"]


def unit(s, uid):
    flags = s["units"].setdefault(uid, {})
    for f in UNIT_FLAGS:
        flags.setdefault(f, False)
    return flags


def log_session(s, uid, evidence):
    """Record Python written today. Returns True if this started a new coding session."""
    new = today() not in s["sessions"]
    s["sessions"].setdefault(today(), {"unit": uid, "evidence": []})["evidence"].append(evidence)
    append_log(evidence)
    return new


def append_log(line):
    if not LOG.exists():
        LOG.write_text(LOG_HEADER, encoding="utf-8", newline="\n")
    with LOG.open("a", encoding="utf-8", newline="\n") as f:
        f.write(f"- {today()} · {line}\n")


def session_count(s):
    return len(s["sessions"])


def week_count(s):
    this_week = date.today().isocalendar()[:2]
    return sum(date.fromisoformat(d).isocalendar()[:2] == this_week for d in s["sessions"])


def add_app_time(s, seconds):
    s["app_seconds"][today()] = s["app_seconds"].get(today(), 0) + seconds


def app_seconds_today(s):
    return int(s["app_seconds"].get(today(), 0))


def rate_recall(s, key, rating):
    """g = got it (retired for good), s = shaky (back in 3 days), b = blanked (back next time)."""
    rec = s["recall"].setdefault(key, {})
    rec.update(last=rating, seen=today())
    if rating == "g":
        rec["retired"] = True
        rec.pop("due", None)
    else:
        rec["due"] = (date.today() + timedelta(days=3 if rating == "s" else 1)).isoformat()
