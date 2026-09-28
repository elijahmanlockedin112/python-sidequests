"""Optional help from Claude. An emergency tool, never the engine.

Nothing here calls an API. It builds a guarded prompt and copies it to the
clipboard; you paste it into Claude yourself. No per-token bill, no latency
inside the app, and the app works exactly the same if you never use it.
"""
import shutil
import subprocess
import sys

THEMES = "speedcubing, Super Mario Bros. speedruns, Quiz Bowl, AI competitions, or running a small software company"

INTRO = ("I'm learning Python with Harvard's CS50P. This is an original practice exercise "
         "(not a CS50 problem set). You are an emergency helper, not my teacher.")

NO_SOLUTIONS = """Rules for your reply:
- Under 150 words.
- Do NOT write the solution, a corrected version of my program, or code for any part of this task.
- You may quote one line of MY code to point at it.
- End with one question that makes me take the next step myself."""


def _task(q):
    return f"THE TASK ({q['title']}):\n{q['task'].strip()}"


def _code(code):
    return f"MY CODE:\n```python\n{code.rstrip()}\n```"


def bug_prompt(q, code, failure):
    return "\n\n".join([
        INTRO + " I wrote this myself, ran it, used three hints, and I'm still stuck.",
        "Explain what's wrong: point at the specific line and name the idea I'm missing.",
        NO_SOLUTIONS, _task(q), _code(code),
        f"WHAT HAPPENED WHEN I CHECKED IT:\n{failure}",
    ])


def example_prompt(q, code):
    return "\n\n".join([
        INTRO + " I've been stuck on this for a while and have already had hints and pseudocode.",
        "Show me a short worked example of a DIFFERENT, simpler problem that uses the idea I'm "
        "missing: different story, different data, not this task with renamed variables. "
        "Explain it in two or three sentences, then stop. Don't connect it back to my task; "
        "I'll make that jump myself. Don't fix or rewrite my code.",
        _task(q), _code(code),
    ])


def review_prompt(q, code):
    return "\n\n".join([
        INTRO + " My program passes all of the checks.",
        "Review it like a kind senior engineer: at most 3 improvements (naming, structure, "
        "an edge case I missed), one sentence each, most important first. Don't rewrite my "
        "program or show a finished version.",
        _task(q), _code(code),
    ])


def extra_prompt(unit, covered):
    return "\n\n".join([
        f"I'm taking Harvard's CS50P and just worked on {unit['label']}: {unit['title']}.",
        f"Make me ONE original practice challenge that needs {unit['title']}, using only ideas "
        f"from these CS50P weeks: {covered}.",
        f"- Theme it around one of my interests: {THEMES}.\n"
        "- Not a CS50 problem set, and not a remix of one.\n"
        "- Give: a title, a 2-3 sentence story, the exact task (inputs and output format), "
        "one example run, and 3 test inputs with their exact expected output.\n"
        "- No solution, no hints, no starter code.",
    ])


def copy(text):
    """Put text on the clipboard. Returns False if no clipboard tool is available."""
    try:
        if sys.platform == "win32":
            subprocess.run(["clip"], input=text.encode("utf-16-le"), check=True)
        elif sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
        elif shutil.which("wl-copy"):
            subprocess.run(["wl-copy"], input=text.encode("utf-8"), check=True)
        elif shutil.which("xclip"):
            subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode("utf-8"), check=True)
        else:
            return False
        return True
    except (OSError, subprocess.CalledProcessError):
        return False
