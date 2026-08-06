"""
update_check.py

Best-effort check for whether a newer sgsl release is available on
GitHub, via the repo's public "latest release" API endpoint (no auth
needed for a public repo).
"""

import json
import re
import urllib.request
from typing import Callable, Optional

from support import command_log

_LatestReleaseUrl = (
    "https://api.github.com/repos/lenosisnickerboa/sgsl/releases/latest"
)

# GitHub's API rejects requests with no User-Agent header.
_UserAgent = "sgsl-update-check"

_VersionPattern = re.compile(r"(\d+(?:\.\d+)*)")


def _parse_version(text: str) -> Optional[tuple[int, ...]]:
    """Parse a version string like "v1.2.3" or "1.2.3" into a tuple of
    ints (1, 2, 3) for comparison, or None if no version number could
    be found in it at all."""
    match = _VersionPattern.search(text)
    if match is None:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def check_for_update(
    current_version: str,
    timeout: float = 5.0,
    printer: Optional[Callable[[str], None]] = None,
) -> Optional[tuple[str, str]]:
    """Check GitHub for the latest sgsl release.

    `printer`, if given, is used to log the request (see
    support.command_log.run()) the same way bat_runner logs a batch
    command -- the request URL, then "OK"/"FAILED: <error>".

    Returns (new_version, release_url) if it's newer than
    current_version, or None if it isn't, the check failed (offline,
    rate-limited, ...), or either version string couldn't be parsed.
    Never raises -- this is a best-effort, non-critical feature that
    must not affect startup either way."""
    request = urllib.request.Request(
        _LatestReleaseUrl,
        headers={"User-Agent": _UserAgent, "Accept": "application/vnd.github+json"},
    )

    def do_request():
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)

    payload = command_log.run(
        printer or (lambda _line: None),
        f"GET {_LatestReleaseUrl}",
        do_request,
        reraise=False,
    )
    if payload is None:
        return None

    tag_name = payload.get("tag_name")
    release_url = payload.get("html_url")
    if not tag_name or not release_url:
        return None

    latest = _parse_version(tag_name)
    current = _parse_version(current_version)
    if latest is None or current is None or latest <= current:
        return None

    # Strip a leading "v"/"V" for display, if present, so the reported
    # version matches VERSION's own plain "x.y.z" format.
    new_version = tag_name.lstrip("vV")
    return new_version, release_url
