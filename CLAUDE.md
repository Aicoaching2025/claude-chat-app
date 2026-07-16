# Local dev environment gotchas — a real debugging log

This file documents actual errors hit while getting `claude-chat-app` running
locally for the first time in VS Code on macOS, with the exact symptom, the
real cause, and the fix that worked. Written to be reusable in future
projects — the causes here (stacked Python environments, relative imports,
foreground processes, wrong working directory) aren't specific to this repo.

## Real errors, and what actually fixed them

### 1. `python3 -m venv .venv` died with `KeyboardInterrupt`

**Symptom:** venv creation hung during the "install pip into the new
environment" step, got interrupted (Ctrl+C, or the terminal otherwise lost
the process), and left a `.venv` folder that looked like it existed but
didn't actually work.

**Consequence:** `source .venv/bin/activate` right after failed with
`no such file or directory` — the activation script was never created
because the process died before finishing.

**Fix:** delete the incomplete folder and let it run to completion without
touching it:
```bash
rm -rf .venv
python3 -m venv .venv    # let this sit until the prompt returns on its own
```

### 2. `uvicorn` ran the wrong Python despite `(.venv)` showing in the prompt

**Symptom:** the shell prompt clearly showed `(.venv)` active, but running
`uvicorn main:app ...` threw an error whose traceback pointed at
`/Library/Frameworks/Python.framework/...` — a completely different, older,
system-wide Python install, not the project's virtual environment.

**Cause:** Anaconda's `base` environment was also active underneath the
project's `.venv` (visible as the `(base)` prefix in the prompt). With two
Python environments stacked, the shell can resolve a bare command name like
`uvicorn` to whichever one it finds first — which isn't reliably the
innermost/most-recently-activated one, especially in zsh.

**Fix:** call tools through the active interpreter explicitly, instead of by
bare command name:
```bash
python -m uvicorn ...      # not: uvicorn ...
```
`python -m <tool>` uses whatever `python` your shell is currently pointing
at (which does follow venv activation correctly) and lets Python's own
import system find the tool inside that environment, sidestepping shell
PATH lookup entirely. General rule: when more than one Python environment
manager is in play (conda + venv, pyenv + venv, etc.), prefer `python -m X`
over bare `X` for anything installed via pip.

### 3. `ImportError: attempted relative import with no known parent package`

**Symptom:** running `uvicorn main:app` from inside the `backend/` folder
failed on `from . import config` inside `main.py`.

**Cause:** `main.py` used a *relative* import (`from . import config`),
which only resolves when Python loads `main` as part of its package (here,
`backend`). Running it as a bare top-level module named `main` — which is
what happens when your working directory is `backend/` itself — gives
Python no package context for `.` to mean anything.

**Fix:** run it from the repository root, referencing the dotted package
path, not from inside the package's own folder:
```bash
cd ..                                                # up to the repo root
python -m uvicorn backend.main:app --reload --port 8000
```
General rule: any file using relative imports (`from . import x`,
`from .sibling import y`) must be run/imported as part of its package.
Practically: run from the directory *containing* the package, using
`package.module:thing`, not from inside the package's own directory.

### 4. Mistook a running server for a frozen terminal

**Symptom:** after starting uvicorn successfully, the terminal never
returned to a prompt, and new commands couldn't be typed.

**Cause:** nothing was actually wrong — a running server is supposed to sit
in the foreground indefinitely, handling requests, until it's told to
stop. That's not a hang; it's the intended behavior.

**Fix / how to tell the difference:** look for the confirmation line:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```
If that's printed, the "stuck" terminal is actually a successfully running
server — leave it alone (don't Ctrl+C) and open a **second** terminal tab
for whatever else needs to run alongside it (e.g. the frontend's static
file server). Only Ctrl+C a terminal like this when you actually want to
stop that server.

### 5. `ModuleNotFoundError: No module named 'backend'`

**Symptom:** re-ran the corrected `python -m uvicorn backend.main:app`
command after fixing issue #3 above, and got a new error: no module named
`backend`.

**Cause:** simple wrong-working-directory mistake — still inside `backend/`
(visible in the prompt: `... backend %`) when the command needs to run from
the parent directory, where `backend/` is visible *as* a subfolder/package.

**Fix:** check the current directory before rerunning a command that
depends on it — the shell prompt itself usually shows the current folder
name at the end. `cd ..` first, confirm the prompt now ends in the repo
root's name, then rerun.

## Scary-looking output that's actually fine (not errors)

- **`[notice] A new release of pip is available: X -> Y`** — informational
  only, printed after a successful `pip install`. Not an error, doesn't
  mean anything failed. Safe to ignore.
- **`cp backend` with no destination argument** — `cp` requires a source
  *and* a destination to do anything. With only one argument it just prints
  `cp: missing destination file operand` and exits without touching any
  files. A typo like this is a no-op, not something that needs cleanup.

## The pattern underneath most of these

Every real error above traces back to one of three things:
1. **Which Python/environment is actually active** (issues #1, #2)
2. **Which directory the command is run from** (issues #3, #5)
3. **Misreading expected behavior as a failure** (issue #4)

None of these are bugs in the sense of "code that's wrong" — they're
environment/invocation mismatches, which is the overwhelmingly common
category of "it doesn't work" problems in local Python dev. Checking `pwd`
and confirming which Python `which python` / `python -c "import sys;
print(sys.executable)"` resolves to are the two fastest ways to rule this
category out before assuming the code itself is broken.
