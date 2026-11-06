"""The Python behind the poe tasks.

The task definitions in ``poe_tasks/*.toml`` hold names, help lines, declared
arguments and sequences. Anything that needs logic lives here and is run as
``python -m poe_tasks <verb>`` from a ``cmd`` task, because a ``cmd`` is the one
task type that both forwards ``-- extras`` to the command and exposes declared
arguments to it (as environment variables). Python bodies inside TOML strings
did neither, and carried their own traps: a triple-quoted docstring closed the
TOML string, a ``\\n`` was unescaped before Python saw it, and nothing linted
them. See *Adding a new poe task* in ``docs/developer/guide.rst``.

This package is not part of the wheel (``[tool.hatch.build.targets.wheel]``
packages only ``qatrack``), so none of it reaches a site.
"""
