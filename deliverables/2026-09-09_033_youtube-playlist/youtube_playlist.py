"""
youtube_playlist.py — create YouTube playlists programmatically (D033).

YouTube Data API v3. Creating a playlist is a write on behalf of a user, so this
needs OAuth 2.0 — an API key is not enough.

Quota is the real constraint, not rate limits. Every Google Cloud project gets
10,000 units/day by default:

    playlists.insert       50 units
    playlistItems.insert   50 units   (per video)
    search.list           100 units

So one playlist plus N videos costs 50 + 50N, and 199 videos is the hard ceiling
for a default project in one day. Quota is tracked and enforced here rather than
discovered halfway through a run.

Env (same convention as D007 calendar_sync.py):
    GOOGLE_CREDENTIALS_JSON   path to the OAuth client secrets file
    GOOGLE_TOKEN_JSON         path to the cached user token (written on first run)

Neither file is ever committed — see the Security Constraints in CLAUDE.md.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlparse

# Write access to the user's playlists.
SCOPES = ["https://www.googleapis.com/auth/youtube"]

QUOTA_PLAYLIST_INSERT = 50
QUOTA_PLAYLIST_ITEM_INSERT = 50
QUOTA_SEARCH = 100
DAILY_QUOTA_DEFAULT = 10_000

VALID_PRIVACY = ("public", "unlisted", "private")
MAX_TITLE_LEN = 150          # YouTube rejects longer titles

# A video ID is exactly 11 chars of the URL-safe base64 alphabet.
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_PATH_ID_RE = re.compile(r"^/(?:shorts|embed|v)/([A-Za-z0-9_-]{11})")


# ── Parsing ──────────────────────────────────────────────────────────────────

def extract_video_id(value: str) -> str | None:
    """Pull the video ID out of any common YouTube URL form, or a bare ID.

    Returns None for anything that is not a single video — a channel or a
    playlist URL included, since silently treating those as a video ID is how
    you burn quota on requests that cannot succeed.
    """
    if not value:
        return None
    value = value.strip()
    if not value:
        return None

    if _VIDEO_ID_RE.match(value):
        return value

    if "://" not in value:
        value = "https://" + value
    try:
        parsed = urlparse(value)
    except ValueError:
        return None

    host = (parsed.hostname or "").lower().removeprefix("www.").removeprefix("m.")

    if host == "youtu.be":
        candidate = parsed.path.lstrip("/").split("/")[0]
        return candidate if _VIDEO_ID_RE.match(candidate) else None

    if host not in {"youtube.com", "music.youtube.com", "youtube-nocookie.com"}:
        return None

    if parsed.path == "/watch":
        candidate = parse_qs(parsed.query).get("v", [""])[0]
        return candidate if _VIDEO_ID_RE.match(candidate) else None

    match = _PATH_ID_RE.match(parsed.path)
    return match.group(1) if match else None


def parse_video_list(entries: list[str]) -> tuple[list[str], list[str]]:
    """Turn a list of URLs/IDs into (video_ids, unparseable_entries).

    Blank lines and `#` comments are ignored so a plain text file can be used
    as input. Duplicates are dropped, keeping first-seen order — YouTube allows
    the same video twice in a playlist, but that is rarely what was meant, and
    each duplicate costs another 50 units.
    """
    ids: list[str] = []
    seen: set[str] = set()
    skipped: list[str] = []

    for entry in entries:
        text = (entry or "").strip()
        if not text or text.startswith("#"):
            continue
        video_id = extract_video_id(text)
        if not video_id:
            skipped.append(text)
        elif video_id not in seen:
            seen.add(video_id)
            ids.append(video_id)

    return ids, skipped


# ── Quota ────────────────────────────────────────────────────────────────────

def estimate_quota(n_videos: int, create_playlist: bool = True) -> int:
    """Units a run will cost, before spending any of them."""
    total = QUOTA_PLAYLIST_INSERT if create_playlist else 0
    return total + n_videos * QUOTA_PLAYLIST_ITEM_INSERT


def max_videos_for_quota(budget: int, create_playlist: bool = True) -> int:
    """How many videos fit in `budget` units."""
    available = budget - (QUOTA_PLAYLIST_INSERT if create_playlist else 0)
    return max(0, available // QUOTA_PLAYLIST_ITEM_INSERT)


def exceeds_quota(n_videos: int, budget: int = DAILY_QUOTA_DEFAULT,
                  create_playlist: bool = True) -> bool:
    return estimate_quota(n_videos, create_playlist) > budget


# ── Request bodies ───────────────────────────────────────────────────────────

def build_playlist_body(title: str, description: str = "",
                        privacy: str = "private") -> dict:
    if not title or not title.strip():
        raise ValueError("Playlist title must not be empty")
    if len(title) > MAX_TITLE_LEN:
        raise ValueError(f"Playlist title exceeds {MAX_TITLE_LEN} characters")
    if privacy not in VALID_PRIVACY:
        raise ValueError(f"Invalid privacy {privacy!r} — one of {VALID_PRIVACY}")

    return {
        "snippet": {"title": title.strip(), "description": description or ""},
        "status": {"privacyStatus": privacy},
    }


def build_playlist_item_body(playlist_id: str, video_id: str) -> dict:
    return {
        "snippet": {
            "playlistId": playlist_id,
            "resourceId": {"kind": "youtube#video", "videoId": video_id},
        }
    }


# ── Results ──────────────────────────────────────────────────────────────────

@dataclass
class PlaylistResult:
    playlist_id: str
    url: str
    quota_spent: int = QUOTA_PLAYLIST_INSERT


@dataclass
class AddReport:
    added: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)     # (video_id, reason)
    skipped_for_quota: list[str] = field(default_factory=list)
    quota_spent: int = 0
    quota_exhausted: bool = False


# ── API calls ────────────────────────────────────────────────────────────────

def get_service():
    """Authenticated YouTube Data API client.

    Imports the Google libraries lazily so this module stays importable — and
    testable — without them, matching D007's pattern.
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds_file = os.environ.get("GOOGLE_CREDENTIALS_JSON", "credentials.json")
    token_file = os.environ.get("GOOGLE_TOKEN_JSON", "youtube_token.json")

    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(creds_file):
                raise FileNotFoundError(
                    f"OAuth client secrets not found at {creds_file!r}. "
                    "Set GOOGLE_CREDENTIALS_JSON — see README."
                )
            creds = InstalledAppFlow.from_client_secrets_file(
                creds_file, SCOPES).run_local_server(port=0)
        with open(token_file, "w", encoding="utf-8") as fh:
            fh.write(creds.to_json())

    return build("youtube", "v3", credentials=creds)


def create_playlist(service, title: str, description: str = "",
                    privacy: str = "private") -> PlaylistResult:
    """Create an empty playlist. Defaults to private on purpose."""
    body = build_playlist_body(title, description, privacy)
    response = service.playlists().insert(part="snippet,status", body=body).execute()
    playlist_id = response["id"]
    return PlaylistResult(
        playlist_id=playlist_id,
        url=f"https://www.youtube.com/playlist?list={playlist_id}",
    )


def add_videos(service, playlist_id: str, video_ids: list[str],
               quota_budget: int | None = None) -> AddReport:
    """Add videos one by one, surviving individual failures.

    There is no batch endpoint for playlistItems, so each video is its own
    request costing 50 units. A deleted, private or region-blocked video fails
    on its own without taking the rest of the run with it — its 50 units are
    spent either way, which is why the count reflects attempts, not successes.
    """
    report = AddReport()

    for index, video_id in enumerate(video_ids):
        if quota_budget is not None and \
                report.quota_spent + QUOTA_PLAYLIST_ITEM_INSERT > quota_budget:
            report.skipped_for_quota = list(video_ids[index:])
            report.quota_exhausted = True
            break

        report.quota_spent += QUOTA_PLAYLIST_ITEM_INSERT
        try:
            service.playlistItems().insert(
                part="snippet",
                body=build_playlist_item_body(playlist_id, video_id),
            ).execute()
            report.added.append(video_id)
        except Exception as exc:
            report.failed.append((video_id, str(exc)))

    return report
