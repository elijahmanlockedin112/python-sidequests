"""The learning loop, with no UI. server.py serves it as the localhost page."""
import ast
import hashlib
import shutil
import subprocess
from datetime import date, datetime

from . import checker, claude, content, state

ROOT = content.ROOT
TICK_CAP = 30              # seconds one heartbeat from the page can add to "time in this app"
APP_BUDGET = 10 * 60       # seconds a day in here before the page objects
EVIDENCE_DIRS = ("my-code", "experiments", "projects")
SKIP_DIRS = {"__pycache__", "venv", "env", "site-packages", "node_modules"}
# scaffolding level -> (name, list the powers, starter skeleton, checks before the first hint)
SCAFFOLD = {2: ("full", True, True, 1), 1: ("light", True, False, 2), 0: ("none", False, False, 3)}
LADDER = ["Think", "Write something", "Run it", "Read the error / output",
          "Try fixing it, then check again", "Small hint", "Syntax reminder", "Pseudocode",
          "Ask Claude to explain my bug", "Ask Claude for a similar worked example"]
COURSE_OPTIONS = [("lecture", "Watched the lecture / a section"),
                  ("examples", "Worked through the examples"),
                  ("pset_attempted", "Attempted the problem set"),
                  ("pset_done", "Completed the problem set")]


class Refused(Exception):
    """Something the learning flow doesn't allow right now. The message is shown as-is."""


def digest(path):
    return hashlib.sha1(path.read_bytes()).hexdigest() if path.exists() else None


def has_code(path):
    """True if the file has at least one statement that isn't just a docstring."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return True  # broken code is still code you wrote
    except (OSError, UnicodeDecodeError):
        return False
    return any(not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)) for n in tree.body)


class Companion:
    def __init__(self):
        self.s = state.load()
        self.units = content.units()
        self.notes = []  # short lines for the page to show, like "Coding session 3 / 40 logged."

    def save(self):
        state.save(self.s)

    # ── where you are ──
    def current(self):
        """The CS50P unit you're on: the first one whose problem set isn't done."""
        return next((u for u in self.units if not state.unit(self.s, u["id"])["pset_done"]), self.units[-1])

    def index(self, u):
        return self.units.index(u)

    def today_unit(self):
        uid = state.day(self.s).get("unit")
        return content.unit(uid) if uid else self.current()

    def active(self):
        for qid, rec in self.s["sidequests"].items():
            if rec["status"] == "active":
                return content.sidequest(qid), rec
        return None, None

    def require_active(self):
        q, rec = self.active()
        if not q:
            raise Refused("There's no sidequest in progress.")
        return q, rec

    def next_quest(self, u):
        """Next unfinished sidequest: any left behind in earlier units first, then this unit's."""
        for unit in self.units[:self.index(u)] + [u]:
            for q in content.sidequests(unit["id"]):
                if q["id"] not in self.s["sidequests"]:
                    return q
        return None

    def scaffold_level(self):
        n = self.s["independence"]
        return 2 if n == 0 else 1 if n < 3 else 0

    def logged_today(self):
        return state.today() in self.s["sessions"]

    def wrote_code(self, rec):
        path = ROOT / rec["file"]
        return path.exists() and digest(path) != rec["starter"] and has_code(path)

    def evidence_today(self):
        """Python files under my-code/, experiments/, projects/ that you changed today.
        app/ and sidequests/ are never evidence: editing this tool is not learning Python."""
        starters = {r["file"]: r["starter"] for r in self.s["sidequests"].values()}
        found = []
        for d in EVIDENCE_DIRS:
            base = ROOT / d
            for p in sorted(base.rglob("*.py")) if base.exists() else []:
                parts = p.relative_to(base).parts[:-1]
                if any(x in SKIP_DIRS or x.startswith(".") for x in parts):
                    continue
                rel = p.relative_to(ROOT).as_posix()
                if date.fromtimestamp(p.stat().st_mtime) != date.today():
                    continue
                if starters.get(rel) == digest(p) or not has_code(p):
                    continue
                found.append(rel)
        return found

    def count_session(self, u, evidence):
        if state.log_session(self.s, u["id"], evidence):
            self.notes.append(f"Coding session {state.session_count(self.s)} / {state.JOURNEY} logged.")

    # ── home ──
    def home(self):
        day, u = state.day(self.s), self.current()
        p = state.unit(self.s, u["id"])
        return {
            "onboarded": self.s["onboarded"],
            "weeks": [f"{x['label']} · {x['title']}" for x in self.units],
            "unit": {k: u[k] for k in ("label", "title", "url")},
            "status": {"lecture": p["lecture"], "examples": p["examples"],
                       "pset": "done" if p["pset_done"] else "started" if p["pset_attempted"] else "not started"},
            "course_done": bool(day.get("course_done")),
            "course_options": [text for _, text in COURSE_OPTIONS],
            "sidequest": self.sidequest_state(day),
            "journey": {"sessions": state.session_count(self.s), "total": state.JOURNEY,
                        "week": state.week_count(self.s), "target": state.WEEKLY_TARGET,
                        "today": self.logged_today()},
            "app_minutes": state.app_seconds_today(self.s) // 60,
            "over_budget": state.app_seconds_today(self.s) >= APP_BUDGET,
        }

    def sidequest_state(self, day):
        q, rec = self.active()
        if q:
            return {"state": "active", "title": q["title"], "file": rec["file"],
                    "can_skip": bool(day.get("course_done") and not day.get("finished"))}
        if day.get("finished"):
            return {"state": "done", "title": day["finished"]}
        if not day.get("course_done"):
            return {"state": "locked", "evidence": not self.logged_today() and bool(self.evidence_today())}
        if not day.get("recall_done"):
            return {"state": "recall"}
        if self.next_quest(self.today_unit()):
            return {"state": "unlocked"}
        return {"state": "empty", "unit": self.today_unit()["title"]}

    # ── 1. first run ──
    def onboard(self, week):
        if not (isinstance(week, int) and 0 <= week < len(self.units)):
            raise Refused("Pick one of the weeks.")
        self.set_position(week)
        self.s["onboarded"] = True

    def set_position(self, i):
        for n, u in enumerate(self.units):
            flags = state.unit(self.s, u["id"])
            if n < i:
                flags.update(lecture=True, examples=True, pset_attempted=True, pset_done=True)
            else:
                flags["pset_done"] = False

    # ── 2. record what you did ──
    def record_course(self, picked):
        picked = {i for i in picked if isinstance(i, int) and 1 <= i <= 4}
        day = state.day(self.s)
        if day.get("course_done"):
            raise Refused("Today's course work is already logged.")
        if not picked:
            raise Refused("Tick at least one thing you did in CS50P.")
        u = self.current()
        flags = state.unit(self.s, u["id"])
        day["undo"] = dict(flags)
        for i in picked:
            flags[COURSE_OPTIONS[i - 1][0]] = True
        if 4 in picked:
            flags["pset_attempted"] = True
        day.update(course_done=True, unit=u["id"])
        if picked & {3, 4}:
            self.count_session(u, f"{u['label']} {u['title']}: CS50P problem set work (cs50.dev)")
        if 4 in picked and u is not self.units[-1]:
            nxt = self.units[self.index(u) + 1]
            self.notes.append(f"{u['label']} is done in CS50P. Next time the main quest is "
                              f"{nxt['label']}: {nxt['title']}.")

    # ── 3. retrieval check ──
    def due_prompts(self, u, limit=2):
        today = state.today()

        def due(unit):
            out = []
            for p in content.recall(unit["id"]):
                r = self.s["recall"].get(f"{unit['id']}/{p['id']}", {})
                if not r.get("retired") and r.get("due", "") <= today:
                    out.append((0 if r else 1, unit, p))  # missed before -> first
            return out

        current = sorted(due(u), key=lambda t: t[0])
        earlier = sorted((x for unit in self.units[:self.index(u)] for x in due(unit)), key=lambda t: t[0])
        picks = current[:1] + earlier[:1]
        picks += (current[1:] + earlier[1:])[:limit - len(picks)]
        return [(unit, p) for _, unit, p in picks]

    def recall(self):
        """Today's retrieval prompts. Chosen once per day so a reload doesn't reshuffle them."""
        day = state.day(self.s)
        if not day.get("course_done"):
            raise Refused("Log today's CS50P work first.")
        if "recall" not in day:
            day["recall"] = [f"{u['id']}/{p['id']}" for u, p in self.due_prompts(self.today_unit())]
            day["rated"] = []
        prompts = []
        for key in day["recall"]:
            uid, pid = key.split("/", 1)
            p = next(p for p in content.recall(uid) if p["id"] == pid)
            prompts.append({"key": key, "unit": content.unit(uid)["title"], "q": p["q"].strip(),
                            "a": p["a"].strip("\n"), "rated": key in day["rated"]})
        if not prompts:
            day["recall_done"] = True
        return prompts

    def rate(self, key, rating):
        day = state.day(self.s)
        if key not in day.get("recall", []) or key in day.get("rated", []) or rating not in ("g", "s", "b"):
            raise Refused("That retrieval question isn't waiting for a rating.")
        state.rate_recall(self.s, key, rating)
        day["rated"].append(key)
        if len(day["rated"]) == len(day["recall"]):
            day["recall_done"] = True
            self.update_mastery()

    def update_mastery(self):
        """Mastery = every recall prompt retired AND a sidequest solved with no hints."""
        for u in self.units:
            prompts = content.recall(u["id"])
            retired = prompts and all(self.s["recall"].get(f"{u['id']}/{p['id']}", {}).get("retired")
                                      for p in prompts)
            clean = any(r["unit"] == u["id"] and r["status"] == "done" and r["hints"] == 0
                        for r in self.s["sidequests"].values())
            if retired and clean:
                state.unit(self.s, u["id"])["mastery"] = True

    # ── 4. sidequest ──
    def reveal(self):
        if self.sidequest_state(state.day(self.s))["state"] != "unlocked":
            raise Refused("The sidequest isn't unlocked. CS50P work and the retrieval check come first.")
        q = self.next_quest(self.today_unit())
        level = self.scaffold_level()
        name, _, skeleton, _ = SCAFFOLD[level]
        path = ROOT / "my-code" / q["unit"] / q["file"]
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(self.starter(q, skeleton), encoding="utf-8", newline="\n")
        rec = {"status": "active", "unit": q["unit"], "file": path.relative_to(ROOT).as_posix(),
               "revealed": datetime.now().isoformat(timespec="minutes"), "level": level,
               "scaffold": name, "hints": 0, "checks": 0, "checks_at_hint": 0, "starter": digest(path)}
        self.s["sidequests"][q["id"]] = rec
        return self.brief()

    def starter(self, q, skeleton):
        u = content.unit(q["unit"])
        lines = [f"SIDEQUEST: {q['title']}  ({u['label']} · {u['title']})", ""]
        lines += q["task"].strip("\n").splitlines() + ["", "Example:"]
        lines += q["example"].strip("\n").splitlines()
        lines += ["", "Check it on the Python Sidequests page (python quest.py)."]
        text = "\n".join(f"# {line}".rstrip() for line in lines) + "\n"
        if skeleton:
            text += "\n\ndef main():\n    ...\n\n\nmain()\n"
        return text

    def brief(self):
        q, rec = self.require_active()
        u = content.unit(q["unit"])
        folder, name = rec["file"].rsplit("/", 1)
        return {"title": q["title"], "unit": f"{u['label']} · {u['title']}", "scaffold": rec["scaffold"],
                "story": q["story"].strip(), "task": q["task"].strip("\n"), "example": q["example"].strip("\n"),
                "powers": q["powers"] if SCAFFOLD[rec["level"]][1] else None,
                "file": rec["file"], "folder": folder, "name": name,
                "editor": bool(shutil.which("code"))}

    def open_editor(self):
        _, rec = self.require_active()
        code = shutil.which("code")
        if not code:
            raise Refused("VS Code's `code` command isn't on your PATH. Open the file yourself.")
        subprocess.Popen([code, str(ROOT / rec["file"])])

    def check(self):
        q, rec = self.require_active()
        path = ROOT / rec["file"]
        if not path.exists():
            raise Refused(f"Can't find {rec['file']}. Did it move or get renamed?")
        if not self.wrote_code(rec):
            raise Refused("That's still the starter file. The first attempt has to be yours: "
                          "write something, run it, then check.")
        rec["checks"] += 1
        results = checker.run_all(path, q)
        failed = [r for r in results if not r.ok]
        out = {"results": [{"name": r.name, "ok": r.ok} for r in results], "passed": len(results) - len(failed)}
        if failed:
            rec["last_fail"] = checker.describe(failed[0])
            out["failure"] = rec["last_fail"]
        else:
            out["complete"] = self.complete(q, rec)
        return out

    def complete(self, q, rec):
        u = content.unit(q["unit"])
        before = self.scaffold_level()
        rec.update(status="done", completed=datetime.now().isoformat(timespec="minutes"))
        rec.pop("last_fail", None)
        state.unit(self.s, u["id"])["sidequest"] = True
        self.s["independence"] = (self.s["independence"] + 1 if rec["hints"] == 0
                                  else max(0, self.s["independence"] - 1))
        after = self.scaffold_level()
        day = state.day(self.s)
        day.update(finished=q["title"], last_done=q["id"])
        help_used = "no hints" if rec["hints"] == 0 else f"{rec['hints']} rung(s) of help"
        self.count_session(u, f"{u['label']} {u['title']}: sidequest {q['title']} (`{rec['file']}`), {help_used}")
        self.update_mastery()
        if rec["hints"] == 0:
            self.notes.append("Solved with no hints.")
        if after < before:
            self.notes.append(f"Scaffolding drops to: {SCAFFOLD[after][0]}. You've earned less help.")
        elif after > before:
            self.notes.append(f"Scaffolding back to: {SCAFFOLD[after][0]}. It adjusts both ways.")
        self.stage_commit([rec["file"]], f"Complete {u['id']} sidequest: {q['title']}")
        return {"title": q["title"], "extend": q.get("extend", []), "commit": self.commit_preview()}

    # ── stuck: the ladder. The first attempt is always yours. ──
    def ladder(self):
        q, rec = self.require_active()
        used, wrote = rec["hints"], self.wrote_code(rec)
        done = [True, wrote, rec["checks"] > 0, rec["checks"] > 0, rec["checks"] > 1] + [used > i for i in range(5)]
        here = next((n for n, ok in enumerate(done, 1) if not ok), 11)
        rung = 6 + used
        since = rec["checks"] - rec["checks_at_hint"]
        blocked = None
        if rung > 10:
            blocked = ("You've used every rung. Take a break, reread the task, or rewatch the CS50P "
                       "section for this idea. Then try again with fresh eyes.")
        elif not wrote:
            blocked = "Rung 2 first: write something. The first attempt has to be yours."
        elif used == 0 and rec["checks"] < SCAFFOLD[rec["level"]][3]:
            left = SCAFFOLD[rec["level"]][3] - rec["checks"]
            blocked = f"Check it {left} more time{'s' if left > 1 else ''} and read the output before the first hint."
        elif used > 0 and since < (2 if rung == 10 else 1):
            blocked = "Try a fix and check again before the next rung."
        return {"rungs": [{"n": n, "label": label, "done": ok, "here": n == here}
                          for n, (label, ok) in enumerate(zip(LADDER, done), 1)],
                "next": None if blocked else rung,
                "next_label": None if blocked else LADDER[rung - 1],
                "blocked": blocked}

    def take_rung(self, n):
        q, rec = self.require_active()
        if n != self.ladder()["next"]:
            raise Refused("That rung isn't open yet.")
        rec["hints"] += 1
        rec["checks_at_hint"] = rec["checks"]
        out = {"label": LADDER[n - 1]}
        if n <= 8:
            out["text"] = {6: q["hint"], 7: q["syntax"], 8: q["pseudocode"]}[n].strip("\n")
        else:
            code = (ROOT / rec["file"]).read_text(encoding="utf-8")
            out["prompt"] = (claude.bug_prompt(q, code, rec.get("last_fail", "(no failed check recorded)"))
                             if n == 9 else claude.example_prompt(q, code))
        return out

    def prompt(self, kind):
        """A copy-and-paste prompt for Claude: a review of today's finished sidequest, or an extra challenge."""
        if kind == "review":
            qid = state.day(self.s).get("last_done")
            if not qid:
                raise Refused("Finish a sidequest first; then Claude can review it.")
            q, rec = content.sidequest(qid), self.s["sidequests"][qid]
            return claude.review_prompt(q, (ROOT / rec["file"]).read_text(encoding="utf-8"))
        if kind == "extra":
            u = self.today_unit()
            covered = ", ".join(x["title"] for x in self.units[:self.index(u) + 1])
            return claude.extra_prompt(u, covered)
        raise Refused("Unknown prompt.")

    # ── real code outranks practice ──
    def own_code(self, real, files, what):
        evidence = self.evidence_today()
        if not evidence:
            raise Refused("No Python file in my-code/, experiments/ or projects/ changed today. "
                          "Planning to code is not coding. Save what you wrote under projects/ "
                          "(or experiments/), then come back.")
        chosen = [f for f in files if f in evidence] or evidence
        what = (what or "").strip()[:120]
        if not what:
            raise Refused("Say what it is, in one line.")
        u = self.today_unit()
        if real:
            self.s["builds"].append({"date": state.today(), "what": what, "files": chosen})
            state.day(self.s)["finished"] = what
        files_md = ", ".join(f"`{f}`" for f in chosen)
        self.count_session(u, f"{'Built' if real else 'Wrote'}: {what} ({files_md})")
        self.stage_commit(chosen, f"{'Build' if real else 'Add'} {what}")
        return {"commit": self.commit_preview()}

    # ── 5. commit ──
    def git(self, *args):
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")

    def stage_commit(self, paths, message):
        """Remember the commit to offer. The page can only confirm it, never choose the files."""
        state.day(self.s)["commit"] = {"paths": [*paths, "progress"], "message": message}

    def commit_preview(self):
        pending = state.day(self.s).get("commit")
        if not pending or not (ROOT / ".git").exists():
            return None
        remote = bool(self.git("remote").stdout.strip())
        commands = [f"git add {' '.join(pending['paths'])}", f'git commit -m "{pending["message"]}"']
        return {"commands": commands + (["git push"] if remote else [])}

    def commit(self):
        day = state.day(self.s)
        pending = day.pop("commit", None)
        if not pending:
            raise Refused("Nothing is waiting to be committed.")
        self.save()  # progress.json must be on disk before it's committed
        remote = bool(self.git("remote").stdout.strip())
        steps = [["add", "--", *pending["paths"]], ["commit", "-m", pending["message"]]]
        for args in steps + ([["push"]] if remote else []):
            proc = self.git(*args)
            if proc.returncode != 0:
                return {"ok": False, "output": f"git {args[0]} didn't work:\n" + (proc.stderr or proc.stdout).strip()[-500:]}
        return {"ok": True, "output": "Committed and pushed." if remote else "Committed."}

    def skip_commit(self):
        state.day(self.s).pop("commit", None)

    # ── progress ──
    def progress(self):
        cur = self.current()
        rows = []
        for u in self.units:
            p = state.unit(self.s, u["id"])
            rows.append({"label": u["label"], "title": u["title"],
                         "mark": "done" if p["pset_done"] else "here" if u is cur else "todo",
                         "lecture": p["lecture"], "examples": p["examples"],
                         "pset": "done" if p["pset_done"] else "started" if p["pset_attempted"] else "",
                         "sidequest": p["sidequest"], "mastery": p["mastery"]})
        quests = [r for r in self.s["sidequests"].values() if r["status"] == "done"]
        return {"rows": rows,
                "sessions": state.session_count(self.s), "total": state.JOURNEY,
                "week": state.week_count(self.s), "target": state.WEEKLY_TARGET,
                "sidequests": len(quests), "clean": sum(r["hints"] == 0 for r in quests),
                "builds": len(self.s["builds"]),
                "scaffold": SCAFFOLD[self.scaffold_level()][0],
                "app_minutes_total": round(sum(self.s["app_seconds"].values()) / 60),
                "app_minutes_today": state.app_seconds_today(self.s) // 60,
                "maintenance": self.s["maintenance_visits"]}

    def tick(self, seconds):
        if isinstance(seconds, (int, float)) and seconds > 0:
            state.add_app_time(self.s, min(seconds, TICK_CAP))
