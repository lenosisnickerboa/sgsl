"""
process_handler.py

A small Windows-only utility class to list, kill, and start OS processes
based on a command line (path to an executable).

Requires: psutil
    pip install psutil
"""

import os
import subprocess
import threading
import time
from typing import Callable, List, Optional

import psutil

# Avoid popping up a console window for the child process by default.
CREATE_NO_WINDOW = 0x08000000


class ProcessHandler:
    """
    Manage Windows processes associated with a given executable command line.

    Parameters
    ----------
    command_line : str
        The complete path to the executable this handler is responsible for,
        e.g. "C:\\Program Files\\MyApp\\myapp.exe".
    """

    def __init__(self, command_line: str):
        # Windows paths are case-insensitive, so normalize case as well as
        # path separators for reliable comparisons.
        self.command_line = os.path.normcase(os.path.normpath(command_line))

    def list_pids(self) -> List[int]:
        """
        List all currently running processes whose executable path matches
        this handler's command_line, and return their PIDs.

        Returns
        -------
        List[int]
            PIDs of matching running processes.
        """
        matching_pids = []

        for proc in psutil.process_iter(attrs=["pid", "exe", "cmdline"]):
            try:
                exe_path = proc.info.get("exe")
                cmdline = proc.info.get("cmdline")

                # Match either the resolved executable path, or the first
                # element of the process's cmdline (in case exe() fails,
                # e.g. due to permissions).
                if exe_path and os.path.normcase(os.path.normpath(exe_path)) == self.command_line:
                    matching_pids.append(proc.info["pid"])
                elif cmdline and os.path.normcase(os.path.normpath(cmdline[0])) == self.command_line:
                    matching_pids.append(proc.info["pid"])

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # Process may have terminated, or we lack permission to inspect it.
                continue

        return matching_pids

    def kill_pids(self, pids: List[int], timeout: float = 3.0, force: bool = True) -> List[int]:
        """
        Kill all processes in the given list of PIDs.

        Parameters
        ----------
        pids : List[int]
            PIDs to terminate.
        timeout : float
            Seconds to wait for graceful termination before force-killing.
        force : bool
            If True, force-kill (SIGKILL / terminate) any process that does
            not exit within `timeout` seconds after a polite terminate.

        Returns
        -------
        List[int]
            PIDs that could not be killed (e.g. did not exist, or access denied).
        """
        procs = []
        failed = []

        for pid in pids:
            try:
                procs.append(psutil.Process(pid))
            except psutil.NoSuchProcess:
                # Already gone -- not a failure.
                continue
            except psutil.AccessDenied:
                failed.append(pid)

        # psutil.Process.terminate() maps to Windows TerminateProcess.
        for p in procs:
            try:
                p.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        gone, alive = psutil.wait_procs(procs, timeout=timeout)

        if alive and force:
            for p in alive:
                try:
                    p.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            gone2, alive2 = psutil.wait_procs(alive, timeout=timeout)
            alive = alive2

        failed.extend(p.pid for p in alive)
        return failed

    def start(
        self,
        args: Optional[List[str]] = None,
        no_window: bool = True,
        stdout_callback: Optional[Callable[[str], None]] = None,
        stderr_callback: Optional[Callable[[str], None]] = None,
        on_exit: Optional[Callable[[int, int], None]] = None,
        **popen_kwargs,
    ) -> int:
        """
        Start the process for this handler's command_line with the given
        arguments, optionally streaming stdout/stderr line-by-line to
        callbacks and/or notifying a callback when the process finishes.

        Parameters
        ----------
        args : Optional[List[str]]
            Arguments to pass to the executable (not including the
            executable path itself).
        no_window : bool
            If True (default), suppress a new console window for
            console/CLI executables.
        stdout_callback : Optional[Callable[[str], None]]
            Called with each line of stdout (newline stripped) as it
            arrives. Runs on a background thread -- keep it fast/thread-safe.
            If provided, it is first called once with the full command line
            (executable + args, Windows-quoted) before any actual process
            output, so you have a record of exactly what was launched.
        stderr_callback : Optional[Callable[[str], None]]
            Same as stdout_callback, but for stderr.
        on_exit : Optional[Callable[[int, int], None]]
            Called once the process has terminated, as on_exit(pid, returncode).
            Called after stdout/stderr streams have been fully drained, on a
            background thread.
        **popen_kwargs
            Additional keyword arguments forwarded to subprocess.Popen
            (e.g. cwd, env). Do not pass stdout/stderr/text here if you use
            the callbacks -- they are set automatically.

        Returns
        -------
        int
            The PID of the newly started process.
        """
        args = args or []
        full_command = [self.command_line] + list(args)

        creationflags = popen_kwargs.pop("creationflags", 0)
        if no_window:
            creationflags |= CREATE_NO_WINDOW

        use_streaming = stdout_callback is not None or stderr_callback is not None or on_exit is not None

        if use_streaming:
            if stdout_callback:
                stdout_callback(" ".join(full_command))

            process = subprocess.Popen(
                full_command,
                creationflags=creationflags,
                stdout=subprocess.PIPE if stdout_callback else subprocess.DEVNULL,
                stderr=subprocess.PIPE if stderr_callback else subprocess.DEVNULL,
                text=True,
                bufsize=1,
                **popen_kwargs,
            )

            reader_threads = []

            if stdout_callback and process.stdout is not None:
                t_out = threading.Thread(
                    target=self._stream_reader,
                    args=(process.stdout, stdout_callback),
                    daemon=True,
                )
                t_out.start()
                reader_threads.append(t_out)

            if stderr_callback and process.stderr is not None:
                t_err = threading.Thread(
                    target=self._stream_reader,
                    args=(process.stderr, stderr_callback),
                    daemon=True,
                )
                t_err.start()
                reader_threads.append(t_err)

            if on_exit is not None:
                watcher = threading.Thread(
                    target=self._wait_and_notify,
                    args=(process, reader_threads, on_exit),
                    daemon=True,
                )
                watcher.start()

        else:
            process = subprocess.Popen(full_command, creationflags=creationflags, **popen_kwargs)

        return process.pid

    @staticmethod
    def _stream_reader(pipe, callback: Callable[[str], None]) -> None:
        """
        Read lines from `pipe` until it closes, invoking `callback` for each
        line (with the trailing newline stripped).
        """
        try:
            for line in iter(pipe.readline, ""):
                if line:
                    callback(line.rstrip("\r\n"))
        finally:
            pipe.close()

    @staticmethod
    def _wait_and_notify(
        process: subprocess.Popen,
        reader_threads: List[threading.Thread],
        on_exit: Callable[[int, int], None],
    ) -> None:
        """
        Wait for `process` to exit and for its stream-reader threads to
        finish (so all buffered output is delivered), then call on_exit.
        """
        returncode = process.wait()
        for t in reader_threads:
            t.join()
        on_exit(process.pid, returncode)


if __name__ == "__main__":
    # Example usage
    handler = ProcessHandler(r"C:\Windows\System32\notepad.exe")

    def handle_stdout(line: str) -> None:
        print(f"[stdout] {line}")

    def handle_stderr(line: str) -> None:
        print(f"[stderr] {line}")

    def handle_exit(pid: int, returncode: int) -> None:
        print(f"Process {pid} exited with code {returncode}")

    pid = handler.start(
        stdout_callback=handle_stdout,
        stderr_callback=handle_stderr,
        on_exit=handle_exit,
    )
    print(f"Started process with PID: {pid}")

    time.sleep(1)

    pids = handler.list_pids()
    print(f"Matching PIDs: {pids}")

    failed = handler.kill_pids(pids)
    print(f"PIDs that failed to be killed: {failed}")