"""
command_log.py

A small helper to consistently log a "command" -- a human-readable,
often literally shell-syntax description of an operation about to
happen (e.g. a `copy "src" "dst"` line for a shutil.copy2() call) --
run it, and log its outcome. Mirrors how bat_runner.run() echoes each
line of a batch file plus its final exit code, for the many operations
that aren't run through an actual .bat file.
"""

from typing import Callable, TypeVar

T = TypeVar("T")


def run(
    printer: Callable[[str], None],
    command: str,
    action: Callable[[], T],
    *,
    reraise: bool = True,
) -> T:
    """Print `command`, call `action()`, print its outcome, then
    return whatever action() returned.

    If action() raises, the exception is printed as the outcome
    (`"FAILED: <exception>"`) and then, if `reraise` is True (the
    default), re-raised -- set it False for a deliberately best-effort
    action (e.g. cleaning up a temp file that may not exist) where the
    caller wants the failure logged but not to interrupt whatever
    comes after it; the return value is None in that case."""
    printer(command)
    try:
        result = action()
    except Exception as e:
        printer(f"FAILED: {e}")
        if reraise:
            raise
        return None
    else:
        printer("OK")
        return result
