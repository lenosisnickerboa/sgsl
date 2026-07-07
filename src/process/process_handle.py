import subprocess
import threading
from typing import Callable, Optional, List, Union

try:
    import psutil
except ImportError:
    psutil = None


class ProcessHandle:
    """Handle to a running (or finished) process tree, allowing kill/wait/status checks."""

    def __init__(self, process: subprocess.Popen):
        self._process = process
        self._done_event = threading.Event()
        self._returncode: Optional[int] = None
        self._lock = threading.Lock()

    def _mark_done(self, returncode: int):
        with self._lock:
            self._returncode = returncode
        self._done_event.set()

    @property
    def pid(self) -> int:
        return self._process.pid

    def is_running(self) -> bool:
        return self._process.poll() is None

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

    def wait(self, timeout: Optional[float] = None) -> Optional[int]:
        """Block until the process finishes (or timeout expires). Returns exit code."""
        finished = self._done_event.wait(timeout=timeout)
        if not finished:
            return None
        return self._returncode

    @property
    def returncode(self) -> Optional[int]:
        with self._lock:
            return self._returncode


def run_command_interactive(
    command: Union[str, List[str]],
    on_output: Callable[[str, str], None],
    on_done: Optional[Callable[[int], None]] = None,
    shell: bool = False,
    cwd: Optional[str] = None,
    env: Optional[dict] = None,
) -> ProcessHandle:
    """
    Spawn a command in the background on Windows, streaming output to a callback.
    Returns immediately with a ProcessHandle you can use to kill (whole tree)/wait on it.

    Args:
        command: Command to run - a string (if shell=True) or list of args.
        on_output: Called as on_output(line, stream) for each line of output,
                   where stream is 'stdout' or 'stderr'. Called from a
                   background thread, in real time.
                   NOTE: MUST use lock in callback if doing something which isn't thread-safe (like updating a GUI).
        on_done: Optional callback called as on_done(returncode) once the
                 process has fully exited. Called from a background thread.
        shell: Whether to run the command through the shell (cmd.exe).
        cwd: Working directory for the command.
        env: Environment variables (dict) for the command.

    Returns:
        A ProcessHandle for controlling/inspecting the running process tree.
    """
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