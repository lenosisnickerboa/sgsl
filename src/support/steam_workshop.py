"""
steam_workshop.py

Looks up details of a Steam Workshop item (a map or a collection)
given its numeric id, via Valve's public GetPublishedFileDetails
endpoint -- no API key needed, unlike most of the Steam Web API.

confirm_workshop_item() builds on this to show the user everything
Valve has on file for an item -- plus sgsl's best guess at whether
it's compatible with whichever of CS2/the re-released CS:GO is asking
(they don't share Workshop maps -- CS2 uses Source 2, CS:GO the
original engine), and why -- in a modal dialog, letting them accept or
reject actually adding it.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Optional

from support.dialog import confirm_dialog

_GetPublishedFileDetailsUrl = (
    "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
)

# Same reasoning as support/wget.py's _UserAgent: a default
# "Python-urllib/x.y" user agent gets rejected by some hosts.
_UserAgent = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@dataclass
class PublishedFileDetails:
    """The subset of Valve's GetPublishedFileDetails response sgsl
    actually shows/uses for a Workshop item (a map or a collection)."""

    workshop_id: int
    title: str
    time_created: int  # unix timestamp, 0 if unknown
    time_updated: int  # unix timestamp, 0 if unknown
    tags: list[str] = field(default_factory=list)
    subscriptions: int = 0


def fetch_published_file_details(
    workshop_id: int, timeout: float = 5.0
) -> Optional[PublishedFileDetails]:
    """Everything sgsl cares about that Valve has on file for Workshop
    item `workshop_id`, or None if it can't be determined -- the id
    doesn't exist, the request fails, or the network is unreachable.
    Never raises."""
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

    entry = details[0]
    return PublishedFileDetails(
        workshop_id=workshop_id,
        title=entry.get("title") or "",
        time_created=entry.get("time_created") or 0,
        time_updated=entry.get("time_updated") or 0,
        tags=[tag.get("tag", "") for tag in entry.get("tags", [])],
        subscriptions=entry.get("subscriptions") or 0,
    )


# CS2 fully replaced CS:GO under the same Steam App ID (730) on this
# date -- there's no "engine version"/"is this a CS2 map" field in the
# API response, so this is the best available anchor for guessing
# whether an item predates CS2 (see _guess_cs2_compatibility()).
_Cs2ReleaseDate = date(2023, 9, 27)


def _to_date(timestamp: int) -> Optional[date]:
    return datetime.fromtimestamp(timestamp, timezone.utc).date() if timestamp else None


def _guess_cs2_compatibility(details: PublishedFileDetails) -> tuple[str, str]:
    """sgsl's best guess at whether `details` is a CS2-native map, and
    why -- there's no reliable, authoritative signal for this (see
    module docstring), so this is a heuristic, not a certainty:

    - An explicit "Cs2"/"Csgo" tag is opt-in by the item's author at
      publish/edit time -- telling, when present, but its absence
      proves nothing (most old, still-popular CS:GO maps were simply
      never retagged).
    - Failing that, time_updated/time_created relative to CS2's
      release date is the next best signal -- but an old map can still
      have been quietly recompiled for CS2 without a tag change, and
      "created after CS2 shipped" only rules out the map being
      CS:GO-only, not that it might still misbehave for other reasons.
    """
    tags_lower = {tag.lower() for tag in details.tags}
    if "cs2" in tags_lower:
        return ("Likely a CS2 map", 'Tagged "Cs2" by its author.')
    if "csgo" in tags_lower:
        return (
            "Likely a pre-CS2 (CS:GO) map -- may not work correctly",
            'Tagged "Csgo" (not "Cs2") by its author.',
        )

    created = _to_date(details.time_created)
    updated = _to_date(details.time_updated)
    if updated is not None and updated >= _Cs2ReleaseDate:
        return (
            "Possibly a CS2 map, but not certain",
            f"No engine tag set, but last updated on {updated}, after CS2's "
            f"release date {_Cs2ReleaseDate} -- it may have been ported since.",
        )
    if created is not None and created >= _Cs2ReleaseDate:
        return (
            "Likely a CS2 map",
            f"Published on {created}, after CS2's release date "
            f"{_Cs2ReleaseDate} -- it didn't exist in the CS:GO era.",
        )
    if created is not None:
        return (
            "Likely a pre-CS2 (CS:GO) map -- may not work correctly",
            f"Published on {created} and never updated since, before CS2's "
            f"release date {_Cs2ReleaseDate}.",
        )
    return ("Unknown", "No creation date information available.")


def _guess_csgo_compatibility(details: PublishedFileDetails) -> tuple[str, str]:
    """Same idea as _guess_cs2_compatibility(), but for the
    re-released standalone CS:GO app -- CS2 workshop maps generally
    don't work there (Source 2 vs. CS:GO's original engine), so the
    verdict is the mirror image: a map that looks CS2-native is the
    *bad* sign here, and one that looks like a classic pre-CS2 CS:GO
    map is the *good* sign. Same underlying signals and caveats as
    _guess_cs2_compatibility(), just reversed."""
    tags_lower = {tag.lower() for tag in details.tags}
    if "csgo" in tags_lower:
        return ("Likely a CS:GO map", 'Tagged "Csgo" by its author.')
    if "cs2" in tags_lower:
        return (
            "Likely a CS2 map -- may not work correctly in CS:GO",
            'Tagged "Cs2" (not "Csgo") by its author.',
        )

    created = _to_date(details.time_created)
    updated = _to_date(details.time_updated)
    if updated is not None and updated >= _Cs2ReleaseDate:
        return (
            "Possibly a CS2-only map -- may not work correctly in CS:GO",
            f"No engine tag set, but last updated on {updated}, after CS2's "
            f"release date {_Cs2ReleaseDate} -- it may have been ported to "
            "Source 2 since.",
        )
    if created is not None and created >= _Cs2ReleaseDate:
        return (
            "Likely a CS2 map -- may not work correctly in CS:GO",
            f"Published on {created}, after CS2's release date "
            f"{_Cs2ReleaseDate} -- it didn't exist in the CS:GO era.",
        )
    if created is not None:
        return (
            "Likely a CS:GO map",
            f"Published on {created} and never updated since, before CS2's "
            f"release date {_Cs2ReleaseDate}.",
        )
    return ("Unknown", "No creation date information available.")


def _format_workshop_details_message(
    details: PublishedFileDetails, verdict: str, reason: str
) -> str:
    lines = [
        f"Title: {details.title or '(untitled)'}",
        f"Workshop ID: {details.workshop_id}",
    ]
    created = _to_date(details.time_created)
    if created is not None:
        lines.append(f"Created: {created}")
    updated = _to_date(details.time_updated)
    if updated is not None:
        lines.append(f"Last updated: {updated}")
    if details.tags:
        lines.append(f"Tags: {', '.join(details.tags)}")
    lines.append(f"Subscribers: {details.subscriptions:,}")
    lines.append("")
    lines.append(f"Verdict: {verdict}")
    lines.append(reason)
    return "\n".join(lines)


def confirm_workshop_item(
    workshop_id: int, target_game: str = "cs2", timeout: float = 5.0
) -> Optional[str]:
    """Fetch full details for Workshop item `workshop_id` and show them
    to the user in a modal confirmation dialog -- including sgsl's
    best guess at whether it'll work in `target_game` ("cs2" or
    "csgo" -- the re-released standalone CS:GO app, whose Workshop
    maps generally aren't interchangeable with CS2's; see
    _guess_cs2_compatibility()/_guess_csgo_compatibility()) -- letting
    them accept or reject actually adding it.

    Returns the item's title (or None if Valve has none on file) if
    the user confirms. Raises ValueError if the user cancels -- the
    same "reject this value" contract ConfigItem.transform expects
    (see config/config_item.py), so using this as a transform makes a
    cancelled confirmation naturally abort the add.

    If details couldn't be fetched at all (offline, bad id, Steam API
    hiccup, ...), no dialog is shown and this silently returns None --
    the caller is expected to fall back to a placeholder name, the
    same as if the id simply had no title on file."""
    details = fetch_published_file_details(workshop_id, timeout=timeout)
    if details is None:
        return None
    guess = _guess_csgo_compatibility if target_game == "csgo" else _guess_cs2_compatibility
    verdict, reason = guess(details)
    message = _format_workshop_details_message(details, verdict, reason)
    if not confirm_dialog(message, title="Add workshop item?"):
        raise ValueError(f"Adding workshop item {workshop_id} was cancelled")
    return details.title or None
