"""
run_command.py

Splits a launch-command string (custom pre/post args, or the full
command line after an "edit run command" dialog) into argv tokens.
"""

import shlex


def split_run_command(command: str) -> list[str]:
    """Split `command` into argv tokens, Windows-path-safe.

    shlex.split()'s default POSIX mode treats a backslash as an escape
    character, so a Windows path like "C:\\Users\\foo\\bar" silently
    loses every backslash ("C:Usersfoobar") -- exactly the kind of
    string these commands are full of (server directories, workshop
    map ids, ...). posix=False leaves backslashes alone, but then
    doesn't strip the quotes around a quoted argument (e.g. an auth
    key containing spaces) the way posix mode would -- so those are
    stripped here instead, same as a real Windows argv parser would."""
    tokens = shlex.split(command, posix=False)
    return [
        token[1:-1] if len(token) >= 2 and token[0] == token[-1] == '"' else token
        for token in tokens
    ]
