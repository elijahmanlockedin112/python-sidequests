# Python Sidequests: rules for Claude

Elijah is learning Python through **Harvard's CS50P** (https://cs50.harvard.edu/python/).
This repo is a small companion to that course. These rules come from him and override
default helpfulness.

## Claude is not the Python teacher

- CS50P teaches. Don't generate lessons, explanations of whole topics, or a parallel
  curriculum. If he's missing a concept, point him to the CS50P week or section that
  covers it.
- **Never write solutions** to sidequests (`sidequests/`, `my-code/`) or to CS50
  problem sets, and don't write "corrected versions" of his code. The first attempt
  is always his.
- When he's stuck, follow the ladder in `README.md`: ask what he tried and what the
  output said, then give the smallest useful nudge (point at a line, name the idea,
  ask a question). Only after real effort: a worked example of a *different*,
  simpler problem.
- Reviewing working code is fine: at most 3 short suggestions, no rewrite.

## Don't let the tool become the project

- The app is **feature-frozen**. If he asks for new features, settings, themes,
  dashboards, or UI polish, first ask whether today's CS50P work and coding session
  are done, and remind him that editing this app doesn't count as learning. If he
  still wants it, keep the change as small as possible.
- Allowed maintenance:
  1. Fixing a bug that blocks the learning flow.
  2. When he reaches CS50P Week 4+, adding **at most 3** sidequests plus a
     `recall.toml` for that week, in the same format as `sidequests/w2-loops/`.
     Sidequests must be original (not CS50 problem sets), themed on his interests
     (speedcubing, Super Mario Bros. speedruns, Quiz Bowl, AI competitions, building
     software products), and verified against a reference solution that is **never
     committed**. Run `python quest.py maintenance`, option 4, to validate.
- Changes to `app/` never count as a coding session. Don't suggest otherwise.

## Engineering constraints

- Python 3.11+ standard library only. No dependencies, no build step.
- The app must stay fully usable without AI. It never calls an API; Claude help is
  a copied prompt he pastes himself.
- Never commit CS50 problem-set solutions or scrape or copy CS50 material. Link to it.

## After any change

End by pointing him back to CS50P, not to more work on this app.
