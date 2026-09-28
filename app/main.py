"""Python Sidequests: the CS50P companion.

Learning Mode (default):  python quest.py
Maintenance Mode:         python quest.py maintenance
"""
import ast
import hashlib
import os
import shutil
import subprocess
import sys
import time
import webbrowser
from datetime import date, datetime

from . import checker, claude, content, state

ROOT = content.ROOT
PROMPT_CAP = 90            # seconds: the most one prompt can add to "time in this app"
APP_BUDGET = 10 * 60       # seconds a day in here before the home screen objects
EVIDENCE_DIRS = ("my-code", "experiments", "projects")
SKIP_DIRS = {"__pycache__", "venv", "env", "site-packages", "node_modules"}
# scaffolding level -> (name, list the powers, starter skeleton, checks before the first hint)
SCAFFOLD = {2: ("full", True, True, 1), 1: ("light", True, False, 2), 0: ("none", False, False, 3)}
LADDER = ["Think", "Write something", "Run it", "Read the error / output",
          "Try fixing it, then check again", "Small hint", "Syntax reminder", "Pseudocode",
          "Ask Claude to explain my bug", "Ask Claude for a similar worked example"]

# ── terminal ──────────────────────────────────────────────────────────────
COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ
if COLOR and os.name == "nt":
    os.system("")  # switches on ANSI colours in the Windows console


def _paint(code):
    return lambda text: f"\033[{code}m{text}\033[0m" if COLOR else str(text)


bold, dim, green, yellow, cyan, red = map(_paint, ("1", "2", "32", "33", "36", "31"))
RULE = dim("─" * 48)


def clear():
    if COLOR:
        print("\033[2J\033[H", end="")


def block(text, indent="  "):
    for line in text.strip("\n").splitlines():
        print(indent + line)


def tick(flag):
    return green("✓") if flag else dim("·")


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


class App:
    def __init__(self):
        self.s = state.load()
        self.units = content.units()

    # ── input with a stopwatch: this app measures its own share of your time ──
    def ask(self, prompt="> "):
        start = time.monotonic()
        try:
            answer = input(prompt)
        except EOFError:
            print()
            raise KeyboardInterrupt
        state.add_app_time(self.s, min(time.monotonic() - start, PROMPT_CAP))
        return answer.strip()

    def pause(self):
        self.ask(dim("\nEnter to go back "))

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

    def next_quest(self, u):
        """Next unfinished sidequest: this unit first, then any left behind in earlier units."""
        for unit in [u] + self.units[:self.index(u)]:
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

    # ── home ──
    def home(self):
        day, unit = state.day(self.s), self.current()
        keys = {"o": self.open_cs50, "p": self.progress}
        clear()
        print(bold("PYTHON SIDEQUESTS"))
        print(dim(f"CS50P · {unit['label']} · {unit['title']}".upper()))
        print(RULE)
        print(bold("MAIN QUEST"))
        print(f"Continue CS50P: {unit['title']}")
        print(dim(self.unit_status(unit)))
        print()
        if day.get("course_done"):
            print(green("✓ Today's course work is logged.") + dim("    [o] open CS50P"))
        else:
            print("[o] OPEN CS50P")
            print(dim("Afterward:"))
            print("[d] I FINISHED TODAY'S COURSE WORK")
            keys["d"] = self.record_course
        print(RULE)
        keys.update(self.sidequest_block(day))
        print(RULE)
        self.journey()
        if state.app_seconds_today(self.s) >= APP_BUDGET:
            print(yellow(f"\n{state.app_seconds_today(self.s) // 60} min in this app today. That's the "
                         "whole budget. Close it and write Python."))
        print(dim("\n[p] progress   [q] quit"))
        return keys

    def unit_status(self, u):
        p = state.unit(self.s, u["id"])
        pset = "done" if p["pset_done"] else "started" if p["pset_attempted"] else "not started"
        return (f"lecture {'✓' if p['lecture'] else '·'}   examples {'✓' if p['examples'] else '·'}"
                f"   problem set: {pset}")

    def sidequest_block(self, day):
        q, rec = self.active()
        if q:
            print(bold(f"SIDEQUEST · {q['title']}"))
            print(dim(rec["file"]))
            print("\n[c] CHECK IT   [s] show the brief   [h] I'm stuck")
            keys = {"c": self.check, "s": lambda: self.show_brief(q, rec, pause=True), "h": self.stuck}
            if day.get("course_done") and not day.get("finished"):
                print(dim("[b] skip it, I built something real"))
                keys["b"] = lambda: self.log_own_code(real=True)
            return keys
        nxt = self.next_quest(self.today_unit())
        unlocked = day.get("course_done") and day.get("recall_done") and not day.get("finished") and nxt
        print(bold("SIDEQUEST UNLOCKED" if unlocked else "SIDEQUEST"))
        if day.get("finished"):
            print(green(f"✓ Done today: {day['finished']}"))
            print(dim("That's the session. Close this and come back next time."))
            return {}
        if not day.get("course_done"):
            print("🔒 Complete today's CS50 work first.")
            if not self.logged_today() and self.evidence_today():
                print(dim("\nYou wrote Python today. [l] log it as a coding session"))
                return {"l": lambda: self.log_own_code(real=False)}
            return {}
        if not day.get("recall_done"):
            print("Unlocks after a 2-5 minute retrieval check.")
            print("\n[k] START THE CHECK")
            return {"k": self.recall}
        if nxt:
            print(cyan("\n   ????\n"))
            print("[r] REVEAL")
            print(dim("[b] skip it, I built something real"))
            return {"r": lambda: self.reveal(nxt), "b": lambda: self.log_own_code(real=True)}
        u = self.today_unit()
        print(f"No premade sidequest for {u['title']}. Real code beats practice.")
        print("\n[b] I BUILT SOMETHING REAL")
        print(dim("[x] ask Claude for an extra challenge (copies a prompt)"))
        return {"b": lambda: self.log_own_code(real=True), "x": self.extra_challenge}

    def journey(self):
        n, week = state.session_count(self.s), state.week_count(self.s)
        filled = round(12 * min(n, state.JOURNEY) / state.JOURNEY)
        print(dim(f"{state.JOURNEY}-session journey"))
        print("█" * filled + dim("░" * (12 - filled)) + f"  {n} / {state.JOURNEY}"
              + dim(f"    this week {week} / {state.WEEKLY_TARGET}"))
        if self.logged_today():
            print(green("✓ coding session logged today"))

    # ── 1. CS50P first ──
    def open_cs50(self):
        u = self.current()
        webbrowser.open(u["url"])
        print(green(f"\nOpened {u['url']}"))
        print("Go learn. Come back and press [d] when you're done.")
        self.pause()

    # ── 2. record what you did ──
    def record_course(self):
        u = self.current()
        options = [("lecture", "Watched the lecture / a section"),
                   ("examples", "Worked through the examples"),
                   ("pset_attempted", "Attempted the problem set"),
                   ("pset_done", "Completed the problem set")]
        print(bold("\nWHAT DID YOU DO IN CS50P TODAY?") + dim(f"   {u['label']} · {u['title']}"))
        for i, (_, text) in enumerate(options, 1):
            print(f"  {i}  {text}")
        picked = {int(ch) for ch in self.ask(dim("numbers, like 1 3 > ")) if ch in "1234"}
        if not picked:
            return
        flags = state.unit(self.s, u["id"])
        day = state.day(self.s)
        day["undo"] = dict(flags)
        for i in picked:
            flags[options[i - 1][0]] = True
        if 4 in picked:
            flags["pset_attempted"] = True
        day.update(course_done=True, unit=u["id"])
        if picked & {3, 4}:
            self.count_session(u, f"{u['label']} {u['title']}: CS50P problem set work (cs50.dev)")
        if 4 in picked and u is not self.units[-1]:
            nxt = self.units[self.index(u) + 1]
            print(green(f"✓ {u['label']} is done in CS50P. Next time the main quest is "
                        f"{nxt['label']}: {nxt['title']}."))
        state.save(self.s)
        self.recall()

    def count_session(self, u, evidence):
        if state.log_session(self.s, u["id"], evidence):
            print(green(f"✓ Coding session {state.session_count(self.s)} / {state.JOURNEY} logged."))

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
        prompts = self.due_prompts(self.today_unit())
        print(bold("\nRETRIEVAL CHECK") + dim("   2-5 minutes · no looking anything up"))
        if not prompts:
            print("Nothing due. Every prompt you've seen so far is retired.")
        for i, (u, p) in enumerate(prompts, 1):
            print(RULE)
            print(dim(f"{i} of {len(prompts)} · {u['title']}"))
            block(p["q"])
            print(dim("\nAnswer in your head, on paper, or in a Python REPL."))
            self.ask(dim("Enter when you have your answer > "))
            print(bold("A good answer:"))
            block(p["a"], "    ")
            rating = ""
            while rating not in ("g", "s", "b"):
                rating = self.ask("[g] got it   [s] shaky   [b] blanked > ").lower()[:1]
            state.rate_recall(self.s, f"{u['id']}/{p['id']}", rating)
        state.day(self.s)["recall_done"] = True
        self.update_mastery()
        state.save(self.s)

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
    def reveal(self, q):
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
        state.save(self.s)
        self.show_brief(q, rec, pause=False)
        code = shutil.which("code")
        if code and self.ask(dim("\n[e] open it in VS Code, Enter to go back > ")).lower() == "e":
            subprocess.Popen([code, str(path)])

    def starter(self, q, skeleton):
        u = content.unit(q["unit"])
        lines = [f"SIDEQUEST: {q['title']}  ({u['label']} · {u['title']})", ""]
        lines += q["task"].strip("\n").splitlines() + ["", "Example:"]
        lines += q["example"].strip("\n").splitlines() + ["", "Check it:  python quest.py  ->  [c]"]
        text = "\n".join(f"# {line}".rstrip() for line in lines) + "\n"
        if skeleton:
            text += "\n\ndef main():\n    ...\n\n\nmain()\n"
        return text

    def show_brief(self, q, rec, pause=True):
        u = content.unit(q["unit"])
        clear()
        print(bold(f"SIDEQUEST · {q['title'].upper()}"))
        print(dim(f"{u['label']} · {u['title']} · scaffolding: {rec['scaffold']}"))
        print()
        block(q["story"], "")
        print(bold("\nTHE TASK"))
        block(q["task"])
        print(bold("\nEXAMPLE"))
        block(q["example"])
        if SCAFFOLD[rec["level"]][1]:
            print(bold("\nPOWERS YOU'LL USE"))
            print("  " + "   ".join(q["powers"]))
        else:
            print(dim("\nPowers: you decide which ones you need."))
        folder, name = rec["file"].rsplit("/", 1)
        print(bold("\nYOUR FILE") + f"   {rec['file']}")
        print(dim(f"  Run it yourself first:   cd {folder}   then   python {name}"))
        print(dim("  Then come back here and press [c] to check it."))
        if pause:
            self.pause()

    def check(self):
        q, rec = self.active()
        path = ROOT / rec["file"]
        print(bold(f"\nCHECKING {path.name}"))
        if not path.exists():
            print(red(f"Can't find {rec['file']}. Did it move or get renamed?"))
            return self.pause()
        if not self.wrote_code(rec):
            print(yellow("That's still the starter file. The first attempt has to be yours: "
                         "write something, run it, then check."))
            return self.pause()
        rec["checks"] += 1
        results = checker.run_all(path, q)
        for i, r in enumerate(results, 1):
            print(f"  {green('✓') if r.ok else red('✗')} {i}  {r.name}")
        failed = [r for r in results if not r.ok]
        if not failed:
            return self.complete(q, rec)
        rec["last_fail"] = checker.describe(failed[0])
        state.save(self.s)
        print()
        block(rec["last_fail"], "    ")
        print(dim(f"\n{len(results) - len(failed)} of {len(results)} pass. "
                  "Read your output, change one thing, run it, check again."))
        self.pause()

    def complete(self, q, rec):
        u = content.unit(q["unit"])
        before = self.scaffold_level()
        rec.update(status="done", completed=datetime.now().isoformat(timespec="minutes"))
        rec.pop("last_fail", None)
        state.unit(self.s, u["id"])["sidequest"] = True
        self.s["independence"] = self.s["independence"] + 1 if rec["hints"] == 0 else max(0, self.s["independence"] - 1)
        after = self.scaffold_level()
        state.day(self.s)["finished"] = q["title"]
        print(green(bold(f"\n✓ ALL CHECKS PASS. {q['title']} complete.")))
        help_used = "no hints" if rec["hints"] == 0 else f"{rec['hints']} rung(s) of help"
        self.count_session(u, f"{u['label']} {u['title']}: sidequest {q['title']} (`{rec['file']}`), {help_used}")
        self.update_mastery()
        state.save(self.s)
        if rec["hints"] == 0:
            print("Solved with no hints.")
        if after < before:
            print(f"Scaffolding drops to: {SCAFFOLD[after][0]}. You've earned less help.")
        elif after > before:
            print(dim(f"Scaffolding back to: {SCAFFOLD[after][0]}. It adjusts both ways."))
        if q.get("extend"):
            print(bold("\nIF YOU WANT MORE") + dim("   optional, not required"))
            for idea in q["extend"]:
                print(f"  · {idea}")
        self.offer_commit([rec["file"]], f"Complete {u['id']} sidequest: {q['title']}")
        if self.ask(dim("\n[a] ask Claude to review your code (optional), Enter to finish > ")).lower() == "a":
            self.to_claude(claude.review_prompt(q, (ROOT / rec["file"]).read_text(encoding="utf-8")))
            self.pause()

    # ── stuck: the ladder. First attempt is always yours. ──
    def stuck(self):
        q, rec = self.active()
        used, wrote = rec["hints"], self.wrote_code(rec)
        done = [True, wrote, rec["checks"] > 0, rec["checks"] > 0, rec["checks"] > 1] + [used > i for i in range(5)]
        rung = 6 + used  # the next help rung you could take
        here = next((n for n, ok in enumerate(done, 1) if not ok), 11)  # where you actually are
        since = rec["checks"] - rec["checks_at_hint"]
        print(bold("\nSTUCK? One rung at a time."))
        for n, (label, ok) in enumerate(zip(LADDER, done), 1):
            marker = green("✓") if ok else cyan("→") if n == here else " "
            print(f"  {marker} {n:>2}  {label if n <= here else dim(label)}")
        print()
        if rung > 10:
            print("You've used every rung. Take a break, reread the task, or rewatch the CS50P "
                  "section for this idea. Then try again with fresh eyes.")
        elif not wrote:
            print(yellow("Rung 2 first: write something. The first attempt has to be yours."))
        elif used == 0 and rec["checks"] < SCAFFOLD[rec["level"]][3]:
            left = SCAFFOLD[rec["level"]][3] - rec["checks"]
            print(yellow(f"Run [c] {left} more time{'s' if left > 1 else ''} and read the output before the first hint."))
        elif used > 0 and since < (2 if rung == 10 else 1):
            print(yellow("Try a fix and run [c] again before the next rung."))
        elif self.ask(f"[{rung}] take rung {rung}, Enter to go back > ") == str(rung):
            return self.take_rung(q, rec, rung)
        self.pause()

    def take_rung(self, q, rec, rung):
        rec["hints"] += 1
        rec["checks_at_hint"] = rec["checks"]
        state.save(self.s)
        print(bold(f"\n{LADDER[rung - 1].upper()}"))
        if rung <= 8:
            block({6: q["hint"], 7: q["syntax"], 8: q["pseudocode"]}[rung])
            print(dim("\nNow go try it."))
        else:
            code = (ROOT / rec["file"]).read_text(encoding="utf-8")
            prompt = (claude.bug_prompt(q, code, rec.get("last_fail", "(no failed check recorded)"))
                      if rung == 9 else claude.example_prompt(q, code))
            self.to_claude(prompt)
        self.pause()

    def to_claude(self, prompt):
        if claude.copy(prompt):
            print(green("✓ Prompt copied. Paste it into Claude."))
            print(dim("It asks Claude not to write your solution. Keep it that way."))
        else:
            print(dim("Copy this into Claude:\n"))
            print(prompt)

    def extra_challenge(self):
        u = self.today_unit()
        covered = ", ".join(x["title"] for x in self.units[:self.index(u) + 1])
        print(bold("\nEXTRA CHALLENGE"))
        self.to_claude(claude.extra_prompt(u, covered))
        print(f"Write your code in my-code/{u['id']}/, then come back and log it with [b].")
        self.pause()

    # ── real code outranks practice ──
    def log_own_code(self, real):
        print(bold("\nSKIP SIDEQUEST: I BUILT SOMETHING REAL" if real else "\nLOG PYTHON I WROTE TODAY"))
        files = self.evidence_today()
        if not files:
            print(yellow("No Python file in my-code/, experiments/ or projects/ changed today."))
            print("Planning to code is not coding. Save what you wrote under projects/ "
                  "(or experiments/), then come back.")
            return self.pause()
        for i, f in enumerate(files, 1):
            print(f"  {i}  {f}")
        picks = self.ask(dim("which ones? numbers, or Enter for all > ")).replace(",", " ").split()
        chosen = [files[int(x) - 1] for x in picks if x.isdigit() and 0 < int(x) <= len(files)] or files
        what = self.ask("What is it, in one line? > ")
        if not what:
            return
        u = self.today_unit()
        if real:
            self.s["builds"].append({"date": state.today(), "what": what, "files": chosen})
            state.day(self.s)["finished"] = what
        files_md = ", ".join(f"`{f}`" for f in chosen)
        self.count_session(u, f"{'Built' if real else 'Wrote'}: {what} ({files_md})")
        state.save(self.s)
        self.offer_commit(chosen, f"{'Build' if real else 'Add'} {what}")
        self.pause()

    # ── 5. commit ──
    def offer_commit(self, paths, message):
        if not (ROOT / ".git").exists():
            return
        files = [*paths, "progress"]
        has_remote = bool(self.git("remote").stdout.strip())
        print(bold("\nCOMMIT"))
        print(f"  git add {' '.join(files)}")
        print(f'  git commit -m "{message}"')
        if has_remote:
            print("  git push")
        if self.ask("Run it now? [Y/n] ").lower() not in ("", "y", "yes"):
            print(dim("Skipped. Run those yourself when you're ready."))
            return
        for args in (["add", "--", *files], ["commit", "-m", message]) + ((["push"],) if has_remote else ()):
            proc = self.git(*args)
            if proc.returncode != 0:
                print(red(f"git {args[0]} didn't work:"))
                block((proc.stderr or proc.stdout).strip()[-500:], "    ")
                return
        print(green("✓ Committed" + (" and pushed." if has_remote else ".")))

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")

    # ── progress ──
    def progress(self):
        clear()
        cur = self.current()
        print(bold("CS50P"))
        print(dim(f"{'':40}" + "".join(f"{h:^6}" for h in ("lec", "ex", "pset", "side", "mast"))))
        for u in self.units:
            p = state.unit(self.s, u["id"])
            mark = "[✓]" if p["pset_done"] else "[>]" if u is cur else "[ ]"
            pset = green("✓") if p["pset_done"] else yellow("…") if p["pset_attempted"] else dim("·")
            cols = [tick(p["lecture"]), tick(p["examples"]), pset, tick(p["sidequest"]), tick(p["mastery"])]
            name = f"{u['label']:<7} {u['title']}"
            print(f"{mark} {name:<36}" + "".join(f"  {c}   " for c in cols))
        quests = [r for r in self.s["sidequests"].values() if r["status"] == "done"]
        clean = sum(r["hints"] == 0 for r in quests)
        total_min = round(sum(self.s["app_seconds"].values()) / 60)
        level = SCAFFOLD[self.scaffold_level()][0]
        print(RULE)
        print(f"{'Coding sessions':<18}{state.session_count(self.s)} / {state.JOURNEY}"
              + dim(f"    this week {state.week_count(self.s)} / {state.WEEKLY_TARGET}"))
        print(f"{'Sidequests':<18}{len(quests)} done, {clean} with no hints")
        print(f"{'Real builds':<18}{len(self.s['builds'])}")
        print(f"{'Scaffolding':<18}{level}" + dim("   (less help as you solve without hints)"))
        print(f"{'Time in this app':<18}{total_min} min total, {state.app_seconds_today(self.s) // 60} today"
              + dim("   (budget: 5-10% of your Python time)"))
        if self.s["maintenance_visits"]:
            print(f"{'Maintenance':<18}{self.s['maintenance_visits']} visits" + dim("   (not learning)"))
        print(dim("\nThe full record of what you wrote is progress/LOG.md."))
        self.pause()

    # ── first run ──
    def onboard(self):
        clear()
        print(bold("PYTHON SIDEQUESTS"))
        print("A companion to Harvard's CS50P. The course teaches. This sends you back to it,")
        print("checks what you remember, then hands you something to build with it.\n")
        print("Which CS50P week are you working on right now?")
        for i, u in enumerate(self.units):
            print(f"  {i:>2}  {u['label']} · {u['title']}")
        answer = ""
        while not (answer.isdigit() and int(answer) < len(self.units)):
            answer = self.ask("> ")
        self.set_position(int(answer))
        self.s["onboarded"] = True
        state.save(self.s)

    def set_position(self, i):
        for n, u in enumerate(self.units):
            flags = state.unit(self.s, u["id"])
            if n < i:
                flags.update(lecture=True, examples=True, pset_attempted=True, pset_done=True)
            else:
                flags["pset_done"] = False

    # ── learning mode ──
    def run(self):
        if not self.s["onboarded"]:
            self.onboard()
        while True:
            keys = self.home()
            choice = self.ask("\n> ").lower()
            if choice in ("q", "quit", "exit"):
                if not state.day(self.s).get("course_done"):
                    print(dim(f"Next: CS50P, {self.current()['title']}."))
                return
            if choice in keys:
                keys[choice]()
                state.save(self.s)

    # ── maintenance mode: deliberately a little annoying to get into ──
    def maintenance(self):
        clear()
        print(yellow(bold("MAINTENANCE MODE")))
        print("Nothing in here is learning, and nothing in here counts.")
        week = state.week_count(self.s)
        print(f"Coding sessions this week: {week} / {state.WEEKLY_TARGET}.")
        if week < state.WEEKLY_TARGET:
            print(yellow("You're under this week's target. The honest move is to go write Python."))
        if self.ask('\nType "maintain" to continue. Anything else leaves: ').lower() != "maintain":
            return
        self.s["maintenance_visits"] += 1
        state.save(self.s)
        while True:
            print(bold("\nMAINTENANCE"))
            print("  1  Set my CS50P week")
            print("  2  Restart a sidequest (keeps your file, clears its progress)")
            print("  3  Undo today's course-work entry")
            print("  4  Validate the sidequest files")
            print("  q  Back to learning")
            choice = self.ask("> ").lower()
            if choice == "1":
                for i, u in enumerate(self.units):
                    print(f"  {i:>2}  {u['label']} · {u['title']}")
                a = self.ask("week number > ")
                if a.isdigit() and int(a) < len(self.units):
                    self.set_position(int(a))
                    print(green(f"✓ Main quest is now {self.current()['label']}: {self.current()['title']}."))
            elif choice == "2":
                ids = list(self.s["sidequests"])
                for i, qid in enumerate(ids, 1):
                    print(f"  {i}  {qid}  ({self.s['sidequests'][qid]['status']})")
                a = self.ask("which one? > ")
                if a.isdigit() and 0 < int(a) <= len(ids):
                    del self.s["sidequests"][ids[int(a) - 1]]
                    print(green("✓ Cleared. Your file is untouched; the sidequest will come around again."))
            elif choice == "3":
                day = state.day(self.s)
                if "undo" in day:
                    self.s["units"][day["unit"]] = day["undo"]
                    for k in ("undo", "unit", "course_done", "recall_done"):
                        day.pop(k, None)
                    print(green("✓ Today's course-work entry is undone. Any coding session it logged stays."))
                else:
                    print("Nothing to undo today.")
            elif choice == "4":
                problems = content.validate()
                print(green("✓ All sidequest files load and have what they need.") if not problems
                      else "\n".join(red(p) for p in problems))
            elif choice in ("q", ""):
                return
            state.save(self.s)


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if argv and argv[0] not in ("maintenance", "--maintenance"):
        print("Usage:  python quest.py              (learning mode)\n"
              "        python quest.py maintenance  (maintenance mode)")
        return
    app = App()
    try:
        app.maintenance() if argv else app.run()
    except KeyboardInterrupt:
        print()
    finally:
        state.save(app.s)
