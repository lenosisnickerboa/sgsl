"""
steam_app_update_check.py

Best-effort check for whether a newer build of a Steam app is
available than what's currently installed -- used by cs2/csgo (both
plain Steam apps under the hood, unlike VU) to detect a pending server
update without having to actually run steamcmd.

Compares the "buildid" recorded in the app's own
steamapps/appmanifest_<appid>.acf (written by steamcmd/Steam itself
after every install/update) against Steam's public, unauthenticated
ISteamApps/UpToDateCheck Web API -- the same one Steam's own client
and various community tools use for this exact purpose.
"""

import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable, Optional

from game.cs2.config_parser.valve_config_parser import ValveConfigParser
from support import command_log

_UpToDateCheckUrl = "https://api.steampowered.com/ISteamApps/UpToDateCheck/v0001/"


def read_installed_build_id(manifest_path: Path) -> Optional[str]:
    """The "buildid" field from a Steam appmanifest_<appid>.acf file
    (a KeyValues document shaped like `"AppState" { "buildid" "123" ... }`),
    or None if the file doesn't exist yet (not installed) or doesn't
    parse as expected."""
    if not manifest_path.exists():
        return None
    try:
        manifest = ValveConfigParser.read(manifest_path)
    except (OSError, UnicodeDecodeError):
        return None
    app_state = manifest.get("AppState")
    if not isinstance(app_state, dict):
        return None
    build_id = app_state.get("buildid")
    return build_id if isinstance(build_id, str) else None


def check_for_steam_app_update(
    appid: int,
    manifest_path: Path,
    timeout: float = 5.0,
    printer: Optional[Callable[[str], None]] = None,
) -> Optional[bool]:
    """True if a newer build of `appid` is available on Steam than the
    one recorded in `manifest_path`, False if that's still the current
    build, or None if it couldn't be determined (not installed yet,
    offline, API hiccup, ...). Never raises -- this is a best-effort,
    non-critical check that must not affect startup either way.

    `printer`, if given, is used to log the request (see
    support.command_log.run()) the same way bat_runner logs a batch
    command -- the request URL, then "OK"/"FAILED: <error>"."""
    build_id = read_installed_build_id(manifest_path)
    if build_id is None:
        return None
    query = urllib.parse.urlencode({"appid": appid, "version": build_id})
    url = f"{_UpToDateCheckUrl}?{query}"
    request = urllib.request.Request(url)

    def do_request():
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)

    payload = command_log.run(
        printer or (lambda _line: None), f"GET {url}", do_request, reraise=False
    )
    if payload is None:
        return None

    result = payload.get("response")
    if not isinstance(result, dict) or not result.get("success"):
        return None
    up_to_date = result.get("up_to_date")
    if not isinstance(up_to_date, bool):
        return None
    return not up_to_date
