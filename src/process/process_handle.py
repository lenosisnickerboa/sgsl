"""
process_runner.py

Spawn commands in the background on Windows, stream their stdout/stderr
line-by-line to a callback in real time, and manage the resulting process
tree (kill, wait, check-if-already-running).
"""

import subprocess
import threading
import os
from typing import Callable, Optional, List, Union

try:
    import psutil
except ImportError:
    psutil = None


class ProcessAlreadyRunningError(Exception):
    def __init__(self, matches):
        self.matches = matches  # list of psutil.Process objects
        pids = [p.pid for p in matches]
        super().__init__(f"Process already running with PID(s): {pids}")

class ProcessHandle:
    """Handle to a running (or finished) process tree on Windows.

    Provides kill (whole tree), wait/status checks, and a static pre-flight
    check to see if the same executable is already running before spawning.
    """

    def __init__(self, process: subprocess.Popen):
        self._process = process
        self._done_event = threading.Event()
        self._returncode: Optional[int] = None
        self._lock = threading.Lock()

    # --- instance state / lifecycle -----------------------------------

    def _mark_done(self, returncode: int):
        with self._lock:
            self._returncode = returncode
        self._done_event.set()

    @property
    def pid(self) -> int:
        return self._process.pid

    def is_running(self) -> bool:
        return self._process.poll() is None

    @property
    def returncode(self) -> Optional[int]:
        with self._lock:
            return self._returncode

    def wait(self, timeout: Optional[float] = None) -> Optional[int]:
        """Block until the process finishes (or timeout expires). Returns exit code."""
        finished = self._done_event.wait(timeout=timeout)
        if not finished:
            return None
        return self._returncode

    # --- killing the whole process tree --------------------------------

    def kill(self, timeout: float = 5.0):
        """Kill the process AND all its descendants (the whole process tree)."""
        if not self.is_running():
            return

        if psutil is not None:
            self._kill_tree_psutil(timeout)
        else:
            self._kill_tree_taskkill()

    def _kill_tree_psutil(self, timeout: float):
        try:
            parent = psutil.Process(self._process.pid)
        except psutil.NoSuchProcess:
            return

        procs = parent.children(recursive=True) + [parent]

        for p in procs:
            try:
                p.terminate()
            except psutil.NoSuchProcess:
                pass

        gone, alive = psutil.wait_procs(procs, timeout=timeout)

        for p in alive:
            try:
                p.kill()
            except psutil.NoSuchProcess:
                pass

    def _kill_tree_taskkill(self):
        """Fallback if psutil isn't installed: /T = tree, /F = force."""
        subprocess.run(
            ["taskkill", "/PID", str(self._process.pid), "/T", "/F"],
            capture_output=True,
        )

    # --- pre-flight "already running?" check ----------------------------

    @staticmethod
    def _extract_exe(command: Union[str, List[str]]) -> str:
        """Pull just the executable (first token) out of a command, ignoring args."""
        if isinstance(command, (list, tuple)):
            exe = str(command[0]) if command else ""
        else:
            exe = command.strip().split()[0] if command.strip() else ""
        return exe

    @staticmethod
    def find_running(command: Union[str, List[str]]) -> List["psutil.Process"]:
        """
        Check whether the same executable (matched on full path if given,
        otherwise just the filename) is already running. Arguments are ignored.

        Returns a list of matching psutil.Process objects (empty if none found,
        or if psutil isn't installed).
        """
        if psutil is None:
            return []

        target_exe = ProcessHandle._extract_exe(command)
        if not target_exe:
            return []

        target_norm = os.path.normcase(os.path.normpath(target_exe))
        target_basename = os.path.basename(target_norm)
        target_has_path = os.path.dirname(target_exe) != ""

        matches = []
        for proc in psutil.process_iter(["pid", "name", "exe"]):
            try:
                proc_exe = proc.info.get("exe") or ""
                proc_name = proc.info.get("name") or ""

                if target_has_path:
                    # Full path given: require an exact path match
                    if proc_exe and os.path.normcase(os.path.normpath(proc_exe)) == target_norm:
                        matches.append(proc)
                else:
                    # No path given: match on filename only
                    if proc_name.lower() == target_basename.lower():
                        matches.append(proc)
                    elif proc_exe and os.path.basename(proc_exe).lower() == target_basename.lower():
                        matches.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return matches


def run_command_interactive(
    command: Union[str, List[str]],
    on_output: Callable[[str, str], None],
    on_done: Optional[Callable[[int], None]] = None,
    shell: bool = False,
    cwd: Optional[str] = None,
    env: Optional[dict] = None,
    allow_duplicate: bool = False,
) -> ProcessHandle:
    """
    Spawn a command in the background on Windows, streaming output to a callback.
    Returns immediately with a ProcessHandle you can use to kill (whole tree)/wait on it.

    Args:
        command: Command to run - a string (if shell=True) or list of args.
        on_output: Called as on_output(line, stream) for each line of output,
                   where stream is 'stdout' or 'stderr'. Called from a
                   background thread, in real time.
        on_done: Optional callback called as on_done(returncode) once the
                 process has fully exited. Called from a background thread.
        shell: Whether to run the command through the shell (cmd.exe).
        cwd: Working directory for the command.
        env: Environment variables (dict) for the command.
        allow_duplicate: If False (default), checks whether the same executable
            is already running (path-matched if a full path was given, else
            filename-matched; arguments are ignored) and raises
            ProcessAlreadyRunningError if so. Set True to skip this check.

    Returns:
        A ProcessHandle for controlling/inspecting the running process tree.

    Raises:
        ProcessAlreadyRunningError: if a matching process is already running
            and allow_duplicate is False.
    """
    if not allow_duplicate:
        existing = ProcessHandle.find_running(command)
        if existing:
            raise ProcessAlreadyRunningError(existing)

    process = subprocess.Popen(
        command,
        shell=shell,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
    )

    def stream_reader(pipe, stream_name):
        try:
            for line in iter(pipe.readline, ''):
                if line:
                    on_output(line.rstrip('\n'), stream_name)
        finally:
            pipe.close()

    stdout_thread = threading.Thread(
        target=stream_reader, args=(process.stdout, 'stdout'), daemon=True
    )
    stderr_thread = threading.Thread(
        target=stream_reader, args=(process.stderr, 'stderr'), daemon=True
    )

    handle = ProcessHandle(process)

    def waiter():
        stdout_thread.join()
        stderr_thread.join()
        returncode = process.wait()
        handle._mark_done(returncode)
        if on_done:
            on_done(returncode)

    stdout_thread.start()
    stderr_thread.start()
    threading.Thread(target=waiter, daemon=True).start()

    return handle