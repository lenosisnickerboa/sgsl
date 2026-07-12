
from thread.run_async import TaskCancelled, run_async


class TaskRunner:
    def __init__(self, name: str, task, *args, done_cb, progress_cb = None, terminal = None, timeout = None):
        self.name = name
        self.task = task
        self.args = args
        self.done_cb = done_cb
        self.progress_cb = progress_cb
        self.terminal = terminal
        self.timeout = timeout
        self.handle = None

    def terminal_output(self, line: str):
        if self.terminal:
            self.terminal.add_line(line)

    def on_progress(self, pct):
        self.terminal_output(f"Task '{self.name}' has completed {pct}%")
        if self.progress_cb:
            self.progress_cb(pct)

    def on_result(self, result):
        self.terminal_output(f"Task '{self.name}' completed 100% with result: {result}")
        self.done_cb(result)

    def on_error(self, exc):
        if isinstance(exc, TaskCancelled):
            self.terminal_output(f"Task '{self.name}' timed out or was cancelled")
            self.done_cb(False)
        else:
            self.terminal_output(f"Task '{self.name}' failed with exception: {exc}")
            self.done_cb(False)

    def run_async(self):
        self.handle = run_async(
            self.task, *self.args,
            on_result=self.on_result,
            on_error=self.on_error,
            on_progress=self.on_progress,
            timeout=self.timeout
        )
