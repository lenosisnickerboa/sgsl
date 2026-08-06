"""
wget.py

A small utility to download a file from a URL to a target location,
similar in spirit to the `wget` command-line tool.
"""

import urllib.request
from pathlib import Path
from typing import Callable, Optional, Union

# Bytes per read/write chunk while streaming the download.
CHUNK_SIZE = 64 * 1024

# Plenty of hosts (e.g. sites fronted by Cloudflare) reject urllib's
# default "Python-urllib/x.y" User-Agent with a 403 — send a normal
# browser-style one instead.
_UserAgent = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def download(
    url: str,
    target_path: Union[str, Path],
    error_printer: Callable[[str], None],
    progress_callback: Optional[Callable[[int, Optional[int]], None]] = None,
    command_printer: Optional[Callable[[str], None]] = None,
) -> Path:
    """
    Download the file at `url` to `target_path`, streaming it to disk
    in chunks rather than loading it fully into memory.

    Parameters
    ----------
    url : str
        The URL to download.
    target_path : Union[str, Path]
        Full path, including filename, to write the downloaded file to.
        Parent directories are created if they don't already exist.
    error_printer : Callable[[str], None]
        Called with a human-readable message if the HTTP request fails
        (unreachable URL, error status, etc.), so the caller can surface
        it (e.g. print it to a terminal/log window). The error is still
        raised afterwards.
    progress_callback : Optional[Callable[[int, Optional[int]], None]]
        If given, called after each chunk is written as
        progress_callback(bytes_downloaded, total_bytes), where
        total_bytes is None if the server didn't report a Content-Length.
    command_printer : Optional[Callable[[str], None]]
        If given, called once up front with the equivalent wget-style
        command line, before the request is made -- e.g. so a caller
        can echo it to a terminal/log window the same way bat_runner
        echoes the batch commands it runs.

    Returns
    -------
    Path
        The path the file was written to (same as target_path).

    Raises
    ------
    urllib.error.URLError
        If the URL cannot be reached.
    urllib.error.HTTPError
        If the server returns an error status.
    """
    target_path = Path(target_path)
    command = f'wget "{url}" -O "{target_path}"'
    if command_printer is not None:
        command_printer(command)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Download to a temp file first so a failed/interrupted download never
    # leaves a partial file sitting at the final target_path.
    tmp_path = target_path.with_name(target_path.name + ".part")

    request = urllib.request.Request(url, headers={"User-Agent": _UserAgent})
    try:
        with urllib.request.urlopen(request) as response:
            total_bytes = response.length  # Content-Length, or None if unknown
            downloaded = 0

            try:
                with tmp_path.open("wb") as f:
                    while True:
                        chunk = response.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback is not None:
                            progress_callback(downloaded, total_bytes)
            except BaseException:
                tmp_path.unlink(missing_ok=True)
                raise
    except Exception as e:
        error_printer(f"Failed to download {url}: {e} ({command})")
        raise

    tmp_path.replace(target_path)
    if command_printer is not None:
        command_printer(f"OK ({command})")
    return target_path


def download_with_return(
    url: str,
    target_path: Union[str, Path],
    error_printer: Callable[[str], None],
    progress_callback: Optional[Callable[[int, Optional[int]], None]] = None,
    command_printer: Optional[Callable[[str], None]] = None,
) -> bool:
    """
    Same as download(), but never raises: returns True on success and
    False if anything went wrong (bad URL, network error, HTTP error
    status, filesystem error, etc.).

    Parameters
    ----------
    url : str
        The URL to download.
    target_path : Union[str, Path]
        Full path, including filename, to write the downloaded file to.
        Parent directories are created if they don't already exist.
    error_printer : Callable[[str], None]
        Same as download()'s error_printer.
    progress_callback : Optional[Callable[[int, Optional[int]], None]]
        Same as download()'s progress_callback.
    command_printer : Optional[Callable[[str], None]]
        Same as download()'s command_printer.

    Returns
    -------
    bool
        True if the file was downloaded successfully, False otherwise.
    """
    try:
        download(url, target_path, error_printer, progress_callback, command_printer)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    # Example usage
    def show_progress(downloaded: int, total: Optional[int]) -> None:
        if total:
            print(f"\r{downloaded / total:.1%} ({downloaded}/{total} bytes)", end="")
        else:
            print(f"\r{downloaded} bytes", end="")

    path = download(
        "https://www.python.org/static/img/python-logo.png",
        r"C:\temp\python-logo.png",
        error_printer=print,
        progress_callback=show_progress,
    )
    print(f"\nDownloaded to {path}")
