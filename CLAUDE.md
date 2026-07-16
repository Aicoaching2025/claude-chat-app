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

### 6. `[Errno 48] address already in use` when restarting the backend

**Symptom:** after closing a terminal tab (instead of stopping the server
running in it first) and later trying to start the backend again in a new
tab, it failed immediately with an address-already-in-use error on port
8000.

**Cause:** closing a terminal tab directly doesn't necessarily stop the
process that was running in it — it can keep running in the background,
orphaned, still holding the port open, even though there's no visible
terminal for it anymore. The port itself wasn't "used up"; a still-alive
process was squatting on it.

**Fix:** find and stop the orphaned process, then retry:
```bash
lsof -i :8000                # lists whatever's bound to the port, with its PID
kill -9 <PID>                 # stop that specific process
lsof -i :8000                 # confirm nothing's listed anymore
python -m uvicorn backend.main:app --port 8000
```
General rule: **always stop a running dev server with Ctrl+C before closing
its terminal tab or window.** Ports free up immediately and reliably when a
process is stopped properly — they are not a limited resource that gets
"used up," and there's no need to switch to a different port next time.
The failure mode above only happens when the old process never actually
stopped.

### 7. Access-code gate and chat panel both visible at once (CSS bug)

**Symptom:** after "unlocking" with the access code, both the access-code
entry screen and the chat message box appeared on screen simultaneously,
instead of the gate disappearing.

**Cause:** a genuine bug in the frontend CSS, not a usage mistake. The gate
element had `.gate { display: flex }` in the stylesheet, and browsers have
a built-in default rule `[hidden] { display: none }`. Both rules have the
same specificity, and when specificity ties, the site's own CSS (author
styles) wins over the browser's built-in default — so setting the `hidden`
attribute via JavaScript had no visible effect on that element. (A parallel
element, the chat panel, had already been given an explicit fix for this
same tie; the gate element was missed.)

**Fix:** add an explicit override that wins the tie on purpose:
```css
#gate[hidden] {
  display: none;
}
```
General rule: whenever a `hidden` attribute is toggled via JavaScript to
show/hide an element, and that element also has a CSS class setting its own
`display` property, add a matching `#id[hidden] { display: none; }` rule
for every such element — don't assume the browser's default `[hidden]`
behavior will "just work" once a class-based `display` value is in play.

## Scary-looking output that's actually fine (not errors)

- **`[notice] A new release of pip is available: X -> Y`** — informational
  only, printed after a successful `pip install`. Not an error, doesn't
  mean anything failed. Safe to ignore.
- **`cp backend` with no destination argument** — `cp` requires a source
  *and* a destination to do anything. With only one argument it just prints
  `cp: missing destination file operand` and exits without touching any
  files. A typo like this is a no-op, not something that needs cleanup.

## The pattern underneath most of these

Most of the real errors above trace back to one of four things:
1. **Which Python/environment is actually active** (issues #1, #2)
2. **Which directory the command is run from** (issues #3, #5)
3. **Misreading expected behavior as a failure** (issues #4, #6)
4. **Something left running that shouldn't be** (issue #6)

Issues #1 through #6 aren't bugs in the sense of "code that's wrong" —
they're environment/invocation mismatches, which is the overwhelmingly
common category of "it doesn't work" problems in local Python dev.
Checking `pwd`, confirming which Python `which python` / `python -c
"import sys; print(sys.executable)"` resolves to, and checking `lsof -i
:<port>` for orphaned processes are the fastest ways to rule this category
out before assuming the code itself is broken.

**Issue #7 is different** — that one was an actual bug in the shipped code
(a CSS rule missing where a parallel one existed), not an environment
mismatch. Worth keeping the two categories distinct when debugging: first
rule out environment/invocation (fast, mechanical, checklist-able), and
only then suspect the application code itself.
