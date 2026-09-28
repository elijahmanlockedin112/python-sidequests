"""Runs your sidequest program the way a user would: types input in, reads what it prints.

Each check in a sidequest file has:
  stdin   what gets typed in
  expect  text that must appear in the output, in order. Plain text by default;
          "re:" at the start means a regular expression.
  reject  text that must NOT appear (optional)
  show    what correct output looks like, for when it fails
Matching ignores capital letters unless the sidequest sets exact_case = true.
"""
import os
import re
import subprocess
import sys
from dataclasses import dataclass

TIMEOUT = 5


@dataclass
class Result:
    name: str
    ok: bool
    stdin: str = ""
    show: str = ""
    output: str = ""
    problem: str = ""


def _normalize(text):
    if isinstance(text, bytes):
        text = text.decode("utf-8", "replace")
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line.rstrip() for line in lines).strip("\n")


def _find(pattern, text, start, flags):
    """End position of pattern in text at or after start, or -1."""
    if pattern.startswith("re:"):
        m = re.compile(pattern[3:], flags | re.MULTILINE).search(text, start)
        return m.end() if m else -1
    haystack, needle = (text, pattern) if not flags & re.IGNORECASE else (text.lower(), pattern.lower())
    i = haystack.find(needle, start)
    return i + len(needle) if i >= 0 else -1


def run_check(path, check, exact_case=False):
    stdin = check.get("stdin", "")
    result = Result(check["name"], False, stdin, check["show"].strip("\n"))
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    try:
        proc = subprocess.run([sys.executable, path.name], cwd=path.parent, input=stdin,
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=TIMEOUT, env=env)
    except subprocess.TimeoutExpired as e:
        result.output = _normalize(e.stdout)
        result.problem = (f"Still running after {TIMEOUT} seconds. Probably a loop whose "
                          "condition never changes, or a loop with no way out.")
        return result
    except OSError as e:
        result.problem = f"Couldn't start Python on your file: {e}"
        return result
    result.output = _normalize(proc.stdout)
    if proc.returncode != 0:
        err = proc.stderr.strip()
        if "EOFError" in err and "Traceback" in err:
            result.problem = ("Your program asked for more input() than this check types in. "
                              "Count your input() calls, or handle the end of input.")
        else:
            result.problem = "Your program crashed:\n" + "\n".join(err.splitlines()[-6:])
        return result
    flags = 0 if check.get("exact_case", exact_case) else re.IGNORECASE
    pos = 0
    for pattern in check["expect"]:
        pos = _find(pattern, result.output, pos, flags)
        if pos < 0:
            result.problem = "Something the output needs is missing, different, or in the wrong order."
            return result
    for pattern in check.get("reject", []):
        if _find(pattern, result.output, 0, flags) >= 0:
            shown = pattern[3:] if pattern.startswith("re:") else pattern
            result.problem = f"The output contains something it shouldn't here: {shown}"
            return result
    result.ok = True
    return result


def run_all(path, quest):
    return [run_check(path, c, quest.get("exact_case", False)) for c in quest["checks"]]


def describe(result, max_lines=14):
    """A failed check, written for a human."""
    typed = result.stdin.rstrip("\n").split("\n") if result.stdin else []
    lines = result.output.split("\n") if result.output else ["(nothing)"]
    if len(lines) > max_lines:
        lines = lines[:max_lines] + [f"... {len(lines) - max_lines} more lines"]
    parts = [f"Check: {result.name}"]
    if typed:
        parts += ["Typed in:"] + [f"  {t}" for t in typed]
    parts += ["Correct output looks like:"] + [f"  {s}" for s in result.show.split("\n")]
    parts += ["Your output:"] + [f"  | {line}" for line in lines]
    parts += [result.problem]
    return "\n".join(parts)
