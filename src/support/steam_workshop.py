"""
steam_workshop.py

Looks up the human-readable title of a Steam Workshop item (a map or a
collection) given its numeric id, via Valve's public
GetPublishedFileDetails endpoint -- no API key needed, unlike most of
the Steam Web API.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

_GetPublishedFileDetailsUrl = (
    "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
)

# Same reasoning as support/wget.py's _UserAgent: a default
# "Python-urllib/x.y" user agent gets rejected by some hosts.
_UserAgent = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def fetch_published_file_title(
    workshop_id: int, timeout: float = 5.0
) -> Optional[str]:
    """The title Valve has on file for workshop item `workshop_id` (a
    map or a collection), or None if it can't be determined -- the id
    doesn't exist, the request fails, or the network is unreachable.
    Never raises; callers should keep whatever name they already have
    when this returns None."""
    body = urllib.parse.urlencode(
        {"itemcount": 1, "publishedfileids[0]": str(workshop_id)}
    ).encode("ascii")
    request = urllib.request.Request(
        _GetPublishedFileDetailsUrl, data=body, headers={"User-Agent": _UserAgent}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None

    details = payload.get("response", {}).get("publishedfiledetails", [])
    if not details or details[0].get("result") != 1:
        return None
    return details[0].get("title") or None
