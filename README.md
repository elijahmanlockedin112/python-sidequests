# Python Sidequests

A small companion to **[Harvard's CS50P](https://cs50.harvard.edu/python/)**.
CS50P is the course. This is the practice space around it. It is not a Python
course, and Claude is not the teacher.

```
python quest.py
```

That opens the page at **http://localhost:8950** (same look as Locked In). Leave the
terminal window open while you use it; Ctrl+C stops it. Python 3.11+, nothing to install.
The server only listens on your own machine, never your network.

## The loop

1. **Main quest: CS50P.** The app shows where you are in the course and opens the
   official page. Most of your time goes there: lectures, examples, problem sets.
2. **Record it.** Four checkboxes. Seconds, not minutes.
3. **Retrieval check.** Two questions from memory, 2-5 minutes. Get one right and
   it's retired for good. Miss one and it comes back.
4. **Sidequest.** Unlocks only after the course work. An original challenge that
   uses what CS50P just taught you. The app checks it by running your program.
5. **Commit.** The app suggests the commit and can run it for you.

> Learn a power → use it → build something → want the next power → back to the course.

## Rules

- **CS50P first.** The sidequest stays locked until today's course work is logged.
- **A coding session only counts if you wrote Python.** Watching a lecture doesn't
  count. Talking to Claude doesn't count. Editing this app doesn't count.
  *Planning to code is not coding.* Target: 5 sessions a week, 40 on the journey.
  There are no streaks: miss a day and nothing happens, you just continue.
- **The first attempt is yours.** When you're stuck, the ladder goes: think → write →
  run → read the output → fix → small hint → syntax reminder → pseudocode → ask Claude
  about your bug → ask Claude for a *similar* example. Each rung unlocks only after
  you've tried again. Solve sidequests without hints and the app gives you less
  scaffolding next time.
- **Real code beats practice.** Built something of your own instead? Choose
  *"I built something real"*, log it, and commit it. Outgrowing the sidequests is
  the goal.
- **Time budget.** About 60-70% CS50P, 25-35% writing code, and at most 5-10% in this
  app. The app times itself and tells you when you're over.

## Learning mode and maintenance mode

`python quest.py` is **learning mode**, the default: the localhost page. It has no
settings, themes, or editors, on purpose.

`python quest.py maintenance` is **maintenance mode**, and it stays in the terminal
on purpose: set your CS50P week, restart a sidequest, undo a mistaken entry, or
validate the sidequest files. It makes you type `maintain` to get in, and it counts
your visits. Nothing in there is learning.

**Feature freeze.** The app is done. Don't build features for it during study time.
The one planned bit of maintenance is adding sidequests for Week 4 onward once you
get there, at most three per week.

## Folders

```
quest.py          run this
app/              the companion itself (editing it never counts as a session)
  core.py           the learning loop
  server.py         serves it on localhost (127.0.0.1 only)
  web/index.html    the page
sidequests/       original challenges + recall questions, per CS50P week (TOML)
my-code/          your sidequest solutions, one folder per CS50P week
experiments/      scratch: type along with lectures, try ideas
projects/         your own real Python projects, where this is all headed
progress/         progress.json (state) and LOG.md (every piece of Python you wrote)
```

## AI help (optional)

The app never calls an AI. When a ladder rung, a review, or an extra challenge
needs Claude, the page copies a prompt to your clipboard that tells Claude **not**
to write your solution. You paste it into Claude yourself.

## CS50 honesty

The sidequests are original. Nothing from CS50 is copied or bundled here; the app
only links to the course. Don't commit your CS50 problem-set solutions. CS50's
academic honesty policy asks you not to share them. `cs50/` is gitignored if you
want local copies.
