# D033 — YouTube Playlist Builder

Create a YouTube playlist and fill it with videos, from code.

```bash
pip install -r requirements.txt

# preview — parses, dedupes and prices the run. No OAuth, no API calls.
python main.py --title "AI Studio — Research" --from-file videos.txt --dry-run

# for real
python main.py --title "AI Studio — Research" --from-file videos.txt
```

## What you need before it will run

Creating a playlist writes to a user's account, so an API key is **not** enough —
this needs OAuth 2.0.

1. [Google Cloud Console](https://console.cloud.google.com) → new or existing project
2. **APIs & Services → Library** → enable **YouTube Data API v3**
3. **Credentials → Create credentials → OAuth client ID → Desktop app**
4. Download the JSON and point the env var at it:

```bash
export GOOGLE_CREDENTIALS_JSON=/path/to/client_secret.json
export GOOGLE_TOKEN_JSON=/path/to/youtube_token.json   # written on first run
```

First run opens a browser for consent. The token is cached and refreshed after that.

Same env var convention as D007 (calendar sync). **Neither file is ever committed** —
see Security Constraints in `CLAUDE.md`.

## Quota is the real limit

Not rate limits — quota. Every Google Cloud project gets **10,000 units/day** by default:

| Call | Units |
|------|-------|
| `playlists.insert` | 50 |
| `playlistItems.insert` | 50 **per video** |
| `search.list` | 100 |

A playlist plus N videos costs `50 + 50N`, so **199 videos is the hard ceiling for one
day** on a default project. There is no batch endpoint for playlist items — each video
is its own request.

The tool tracks this rather than letting you discover it halfway through:

- `--dry-run` prices the run before you spend anything
- over budget → it says how many will fit, before starting
- hitting the ceiling mid-run → it stops, lists what was not added, and tells you to
  re-run tomorrow with those URLs

Quota resets at midnight Pacific. An increase can be requested in the Cloud Console,
but Google reviews those by hand and usually rejects hobby-scale requests.

## Input formats

Full URLs or bare 11-character IDs:

```
https://www.youtube.com/watch?v=dQw4w9WgXcQ     # extra &list= / &t= params are ignored
https://youtu.be/dQw4w9WgXcQ?t=90
https://www.youtube.com/shorts/dQw4w9WgXcQ
https://www.youtube.com/embed/dQw4w9WgXcQ
dQw4w9WgXcQ
```

In a `--from-file` list, blank lines and `#` comments are ignored. Duplicates are
dropped keeping first-seen order — YouTube would happily add the same video twice, and
charge you 50 units for it.

Channel and playlist URLs are rejected rather than guessed at, since a request built
from one cannot succeed and still costs quota.

## Behaviour worth knowing

- **Private by default.** `--privacy public` is opt-in; an accidentally public playlist
  isn't something the viewer can undo.
- **One bad video doesn't kill the run.** Deleted, private, or region-blocked videos are
  reported individually and the rest still get added. Their 50 units are spent either
  way, which is why the quota count reflects attempts, not successes.
- **Title is validated locally** (non-empty, ≤150 chars) before spending the 50 units on
  a create that YouTube would reject.
- Exit codes: `0` all good, `1` aborted or bad input, `2` completed with per-video failures.

## Files

| File | Purpose |
|------|---------|
| `youtube_playlist.py` | Library: URL parsing, quota maths, request bodies, API calls |
| `main.py` | CLI |
| `requirements.txt` | `google-api-python-client`, `google-auth-oauthlib` |

Tests: `tests/test_033_youtube_playlist.py` — 43 cases, all offline. The Google
libraries are imported lazily inside the auth path, so the module imports and the logic
stays testable without them installed.

## Using it as a library

```python
import youtube_playlist as yp

service = yp.get_service()
playlist = yp.create_playlist(service, "My Playlist", "Description", "unlisted")
ids, skipped = yp.parse_video_list(open("videos.txt").read().splitlines())
report = yp.add_videos(service, playlist.playlist_id, ids, quota_budget=9950)

print(playlist.url, len(report.added), report.failed)
```
