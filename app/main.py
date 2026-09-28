"""Python Sidequests: the CS50P companion.

Learning mode (default):  python quest.py               serves the page on localhost
Maintenance mode:         python quest.py maintenance   stays in the terminal, on purpose
"""
import os
import sys

from . import content, state
from .core import Companion
from .server import serve

COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ
if COLOR and os.name == "nt":
    os.system("")  # switches on ANSI colours in the Windows console


def _paint(code):
    return lambda text: f"\033[{code}m{text}\033[0m" if COLOR else str(text)


bold, green, yellow, red = map(_paint, ("1", "32", "33", "31"))


def ask(prompt):
    try:
        return input(prompt).strip()
    except EOFError:
        raise KeyboardInterrupt


def maintenance(c):
    """Deliberately a little annoying to get into. Nothing in here is learning."""
    print(yellow(bold("MAINTENANCE MODE")))
    print("Nothing in here is learning, and nothing in here counts.")
    week = state.week_count(c.s)
    print(f"Coding sessions this week: {week} / {state.WEEKLY_TARGET}.")
    if week < state.WEEKLY_TARGET:
        print(yellow("You're under this week's target. The honest move is to go write Python."))
    if ask('\nType "maintain" to continue. Anything else leaves: ').lower() != "maintain":
        return
    c.s["maintenance_visits"] += 1
    c.save()
    while True:
        print(bold("\nMAINTENANCE"))
        print("  1  Set my CS50P week")
        print("  2  Restart a sidequest (keeps your file, clears its progress)")
        print("  3  Undo today's course-work entry")
        print("  4  Validate the sidequest files")
        print("  q  Back to learning")
        choice = ask("> ").lower()
        if choice == "1":
            for i, u in enumerate(c.units):
                print(f"  {i:>2}  {u['label']} · {u['title']}")
            a = ask("week number > ")
            if a.isdigit() and int(a) < len(c.units):
                c.set_position(int(a))
                c.s["onboarded"] = True
                print(green(f"✓ Main quest is now {c.current()['label']}: {c.current()['title']}."))
        elif choice == "2":
            ids = list(c.s["sidequests"])
            for i, qid in enumerate(ids, 1):
                print(f"  {i}  {qid}  ({c.s['sidequests'][qid]['status']})")
            a = ask("which one? > ")
            if a.isdigit() and 0 < int(a) <= len(ids):
                del c.s["sidequests"][ids[int(a) - 1]]
                print(green("✓ Cleared. Your file is untouched; the sidequest will come around again."))
        elif choice == "3":
            day = state.day(c.s)
            if "undo" in day:
                c.s["units"][day["unit"]] = day["undo"]
                for k in ("undo", "unit", "course_done", "recall", "rated", "recall_done"):
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
        c.save()


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if argv and argv[0] in ("maintenance", "--maintenance"):
        c = Companion()
        try:
            maintenance(c)
        except KeyboardInterrupt:
            print()
        finally:
            c.save()
    elif not argv or argv == ["--no-browser"]:
        serve(open_browser=not argv)
    else:
        print("Usage:  python quest.py               learning mode (opens the page on localhost)\n"
              "        python quest.py maintenance   maintenance mode")
