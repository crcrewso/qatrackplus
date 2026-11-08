"""The code behind the poe tasks, as code rather than as strings in TOML.

**This package is a demonstration of swift's §4**, not a finished migration.
Four verbs are ported; thirteen bodies are still in `poe_tasks/*.toml`. See
`SHAPE.md` beside this file for what is here, what is not, and what each
measured.

The shape: `poe_tasks/*.toml` keeps what TOML is good at - the task's name, its
help line, its declared arguments with `choices` for tab completion, `env`
tables and sequences - and each task's body becomes a one-line `cmd` calling a
verb here.

Why, each measured on poe 0.49.0 rather than argued:

- **One echoed line instead of the whole body.** poe prints a task's source
  before running it. `test-gui` printed 25 lines; as a `cmd` it prints one.
  Across all seventeen bodies that is 439 lines of Python on the terminal.
- **Arguments forward again.** A `cmd` passes `-- -k foo` through to what it
  runs; a Python body drops it. That is why six `test-gui-<browser>-<mode>`
  tasks became three-plus-an-argument and then one-plus-two-options, each step
  losing the ability to filter to a single test.
- **ruff sees it.** Nothing lints Python inside a TOML string, and the bodies
  include everything destructive the project owns.
- **Tests import functions instead of compiling strings.** `test_poe_tasks.py`
  extracts bodies with `tomllib`, compiles them and runs them through
  subprocess against stand-ins; a module is imported and called.
- **No TOML traps.** No triple quotes that would close the enclosing string, no
  doubled `\\n`, and docstrings instead of `#` comments - which is why this
  module can explain itself at all.

What does *not* move: a task that is already a one-line `cmd` stays one. This is
for the bodies.
"""
