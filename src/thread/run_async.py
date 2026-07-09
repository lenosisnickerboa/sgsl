import time
import threading
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=4)


class CancelToken:
    """Passed into the task so it can check whether it should stop."""
    def __init__(self):
        self._event = threading.Event()

    def cancel(self):
        self._event.set()

    def is_cancelled(self):
        return self._event.is_set()

    def raise_if_cancelled(self):
        if self._event.is_set():
            raise TaskCancelled()


class TaskCancelled(Exception):
    pass


class TaskHandle:
    """Returned to the caller so they can cancel the task manually."""
    def __init__(self, future, token, timer):
        self.future = future
        self._token = token
        self._timer = timer

    def cancel(self):
        self._token.cancel()
        if self.future.cancel():  # in case it hasn't started yet
            if self._timer:
                self._timer.cancel()

    def done(self):
        return self.future.done()


def run_async(func, *args, on_result=None, on_error=None, on_progress=None,
              timeout=None, **kwargs):
    """
    Spawn func(*args, **kwargs) on a background thread.

    func must accept `cancel_token` (a CancelToken) and periodically call
    cancel_token.raise_if_cancelled() to support cancellation/timeout.

    - on_progress(pct): passed into func as `progress_cb`, if func supports it
    - on_result(value): called with the return value on success
    - on_error(exc): called with the exception on failure (including TaskCancelled)
    - timeout: seconds after which the task is auto-cancelled
    """
    token = CancelToken()
    kwargs["cancel_token"] = token
    if on_progress is not None:
        kwargs["progress_cb"] = on_progress

    future = executor.submit(func, *args, **kwargs)

    timer = None
    if timeout is not None:
        timer = threading.Timer(timeout, token.cancel)
        timer.start()

    def _done(fut):
        if timer:
            timer.cancel()
        try:
            result = fut.result()
            if on_result:
                on_result(result)
        except Exception as e:
            if on_error:
                on_error(e)
            else:
                print(f"Task failed: {e}")

    future.add_done_callback(_done)
    return TaskHandle(future, token, timer)