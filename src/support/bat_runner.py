"""
bat_runner.py

A small utility to run a list of command lines as a single Windows
batch (.bat) file.
"""

import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Callable, List, Optional, Union

from process.process_handler import CREATE_NO_WINDOW


def run(
    commands: List[str],
    cwd: Optional[Union[str, Path]] = None,
    output_callback: Optional[Callable[[str], None]] = None,
    done_callback: Optional[Callable[[int], None]] = None,
) -> None:
    """
    Write `commands` to a temporary .bat file and run it on a
    background thread, without blocking the caller.

    Output is read from a plain pipe, so console programs that only
    flush their output when attached to a real terminal (steamcmd.exe
    being the canonical example) will withhold their output until
    their internal buffer fills or they exit, rather than streaming it
    live -- accepted trade-off for avoiding pywinpty/ConPTY, which
    could get a spurious Ctrl+C-style signal (STATUS_CONTROL_C_EXIT)
    delivered to the spawned process tree under a console-less
    ("windowed") PyInstaller build, killing commands almost immediately
    after they start.

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
        then again with each line of the batch file's combined
        stdout/stderr (newline stripped) as it arrives. Runs on a
        background thread -- keep it fast/thread-safe.
    done_callback : Optional[Callable[[int], None]]
        If given, called once as done_callback(exit_code) after the
        batch file has finished. Called after output has been fully
        drained, on a background thread.
    """
    def _emit(line: str) -> None:
        if output_callback is not None:
            output_callback(line)

    with tempfile.NamedTemporaryFile("w", suffix=".bat", delete=False) as f:
        bat_path = Path(f.name)
        for command in commands:
            f.write(command + "\r\n")
            _emit(command)

    def _run_in_background():
        try:
            try:
                process = subprocess.Popen(
                    [str(bat_path)],
                    cwd=str(cwd) if cwd is not None else None,
                    creationflags=CREATE_NO_WINDOW,
                    stdout=subprocess.PIPE if output_callback else subprocess.DEVNULL,
                    stderr=subprocess.STDOUT if output_callback else subprocess.DEVNULL,
                    text=True,
                    bufsize=1,
                )
            except Exception as exc:
                _emit(f"Failed to start batch file: {exc}")
                if done_callback is not None:
                    done_callback(1)
                return

            try:
                if output_callback and process.stdout is not None:
                    for line in iter(process.stdout.readline, ""):
                        if line:
                            _emit(line.rstrip("\r\n"))
                    process.stdout.close()

                exit_code = process.wait()
            except Exception as exc:
                exit_code = 1
                _emit(f"Batch file execution failed: {exc}")

            if done_callback is not None:
                done_callback(exit_code)
        finally:
            bat_path.unlink(missing_ok=True)

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
