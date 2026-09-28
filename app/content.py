"""Reads the CS50P map, sidequests and recall prompts from sidequests/ (TOML, stdlib only)."""
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "sidequests"
QUEST_FIELDS = ("title", "order", "powers", "story", "task", "example",
                "hint", "syntax", "pseudocode", "checks")
_cache = {}


def _toml(path):
    with open(path, "rb") as f:
        return tomllib.load(f)


def units():
    if "units" not in _cache:
        _cache["units"] = _toml(CONTENT / "units.toml")["unit"]
    return _cache["units"]


def unit(uid):
    return next(u for u in units() if u["id"] == uid)


def sidequests(uid):
    """The premade sidequests for one unit, in their intended order."""
    key = ("quests", uid)
    if key not in _cache:
        folder = CONTENT / unit(uid)["dir"]
        quests = []
        for path in sorted(folder.glob("*.toml")) if folder.exists() else []:
            if path.name == "recall.toml":
                continue
            q = _toml(path)
            q["id"] = path.stem
            q["unit"] = uid
            q["file"] = path.stem.replace("-", "_") + ".py"
            quests.append(q)
        _cache[key] = sorted(quests, key=lambda q: q.get("order", 99))
    return _cache[key]


def sidequest(qid):
    for u in units():
        for q in sidequests(u["id"]):
            if q["id"] == qid:
                return q
    return None


def recall(uid):
    path = CONTENT / unit(uid)["dir"] / "recall.toml"
    return _toml(path).get("prompt", []) if path.exists() else []


def validate():
    """Problems in the content files, as readable strings. Empty list = all good."""
    problems, seen = [], set()
    try:
        all_units = units()
    except Exception as e:  # a broken units.toml is the one thing worth catching broadly
        return [f"units.toml: {e}"]
    for u in all_units:
        try:
            quests, prompts = sidequests(u["id"]), recall(u["id"])
        except tomllib.TOMLDecodeError as e:
            problems.append(f"{u['dir']}: {e}")
            continue
        for q in quests:
            where = f"{u['dir']}/{q['id']}.toml"
            if q["id"] in seen:
                problems.append(f"{where}: duplicate sidequest id")
            seen.add(q["id"])
            problems += [f"{where}: missing '{f}'" for f in QUEST_FIELDS if f not in q]
            for i, check in enumerate(q.get("checks", []), 1):
                problems += [f"{where}: check {i} missing '{f}'"
                             for f in ("name", "expect", "show") if f not in check]
        for p in prompts:
            problems += [f"{u['dir']}/recall.toml: prompt missing '{f}'"
                         for f in ("id", "q", "a") if f not in p]
    return problems
