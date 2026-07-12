"""
bat_runner.py

A small utility to run a list of command lines as a single Windows
batch (.bat) file.
"""

import re
import tempfile
import threading
from pathlib import Path
from typing import Callable, List, Optional, Union

from winpty import PtyProcess

# Matches ANSI/VT escape sequences (cursor moves, terminal capability
# queries, etc.) that a pseudo-console injects/relays -- stripped
# before a line reaches output_callback.
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")

# Chars per read while streaming the pseudo-console's output.
READ_SIZE = 1024


def run(
    commands: List[str],
    cwd: Optional[Union[str, Path]] = None,
    output_callback: Optional[Callable[[str], None]] = None,
    done_callback: Optional[Callable[[int], None]] = None,
) -> None:
    """
    Write `commands` to a temporary .bat file and run it on a
    background thread, without blocking the caller.

    The batch file runs inside a Windows pseudo-console (ConPTY)
    rather than a plain pipe, so console programs that only flush
    their output when attached to a real terminal (steamcmd.exe being
    the canonical example) still stream their output as it's
    produced, instead of withholding everything until they exit.

    Parameters
    ----------
    commands : List[str]
        The command lines to execute, in order, one per line, written
        verbatim into the generated .bat file.
    cwd : Optional[Union[str, Path]]
        Working directory to run the batch file from. Defaults to the
        current process's working directory.
    output_callback : Optional[Callable[[str], None]]
        If given, called once (synchronously, before run() returns)
        for each line in `commands` as it's written to the .bat file,
        then again with each line of the batch file's own output
        (ANSI escape sequences and newline stripped) as it arrives.
        Output lines are also split on a bare "\\r" (not just
        "\\r\\n"), since console tools commonly redraw progress that
        way. The output-streaming calls run on a background thread --
        keep the callback fast/thread-safe.
    done_callback : Optional[Callable[[int], None]]
        If given, called once as done_callback(exit_code) after the
        batch file has finished. Called after output has been fully
        drained, on a background thread.
    """
    def _emit(raw_line: str) -> None:
        if output_callback is None:
            return
        line = _ANSI_ESCAPE_RE.sub("", raw_line)
        if line:
            output_callback(line)

    with tempfile.NamedTemporaryFile("w", suffix=".bat", delete=False) as f:
        bat_path = Path(f.name)
        for command in commands:
            f.write(command + "\r\n")
            _emit(command)

    def _run_in_background():
        process = PtyProcess.spawn([str(bat_path)], cwd=str(cwd) if cwd is not None else None)

        buffer = ""
        try:
            while True:
                try:
                    chunk = process.read(READ_SIZE)
                except EOFError:
                    break
                if not chunk:
                    break
                buffer += chunk
                while True:
                    match = re.search(r"[\r\n]", buffer)
                    if not match:
                        break
                    _emit(buffer[: match.start()])
                    buffer = buffer[match.end() :]
            _emit(buffer)
        finally:
            bat_path.unlink(missing_ok=True)

        if done_callback is not None:
            done_callback(process.exitstatus or 0)

    threading.Thread(target=_run_in_background, daemon=True).start()


if __name__ == "__main__":
    # Example usage
    done = threading.Event()

    def on_done(exit_code):
        print(f"Exit code: {exit_code}")
        done.set()

    run(
        ["echo Hello from bat_runner", "dir"],
        output_callback=print,
        done_callback=on_done,
    )
    done.wait()
