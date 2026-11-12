"""Tests for D033 — programmatic YouTube playlist creation.

Everything here runs offline. The Google client libraries are imported lazily
inside the auth path (same pattern as D007 calendar_sync.py), so the module
imports and the logic is testable without google-api-python-client installed.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent
                      / "deliverables" / "2026-09-09_033_youtube-playlist"))

import youtube_playlist as yp


# ── Fakes ────────────────────────────────────────────────────────────────────

class _Call:
    def __init__(self, result, error=None):
        self._result, self._error = result, error

    def execute(self):
        if self._error:
            raise self._error
        return self._result


class FakeYouTube:
    """Mimics the googleapiclient chained interface."""

    def __init__(self, playlist_id="PL_fake", item_errors=None):
        self.playlist_id = playlist_id
        self.item_errors = item_errors or {}     # video_id -> Exception
        self.playlist_bodies = []
        self.item_bodies = []

    def playlists(self):
        outer = self

        class _P:
            def insert(self, part, body):
                outer.playlist_bodies.append((part, body))
                return _Call({"id": outer.playlist_id})
        return _P()

    def playlistItems(self):
        outer = self

        class _I:
            def insert(self, part, body):
                outer.item_bodies.append((part, body))
                vid = body["snippet"]["resourceId"]["videoId"]
                return _Call({"id": f"item_{vid}"}, error=outer.item_errors.get(vid))
        return _I()


# ── Video ID extraction ──────────────────────────────────────────────────────

class TestExtractVideoId:
    @pytest.mark.parametrize("url,expected", [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("http://youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("dQw4w9WgXcQ", "dQw4w9WgXcQ"),                       # bare ID
    ])
    def test_recognised_forms(self, url, expected):
        assert yp.extract_video_id(url) == expected

    def test_extra_query_params_ignored(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLxxx&t=42s"
        assert yp.extract_video_id(url) == "dQw4w9WgXcQ"

    def test_timestamp_on_short_link(self):
        assert yp.extract_video_id("https://youtu.be/dQw4w9WgXcQ?t=90") == "dQw4w9WgXcQ"

    def test_surrounding_whitespace(self):
        assert yp.extract_video_id("  https://youtu.be/dQw4w9WgXcQ  ") == "dQw4w9WgXcQ"

    @pytest.mark.parametrize("bad", [
        "", "   ", "https://vimeo.com/12345", "https://youtube.com/watch?v=",
        "not a url", "https://www.youtube.com/@channel",
    ])
    def test_unrecognised_returns_none(self, bad):
        assert yp.extract_video_id(bad) is None

    def test_playlist_url_is_not_a_video(self):
        assert yp.extract_video_id("https://www.youtube.com/playlist?list=PLabc") is None


class TestParseVideoList:
    def test_dedupes_preserving_order(self):
        ids, skipped = yp.parse_video_list([
            "https://youtu.be/aaaaaaaaaaa",
            "https://www.youtube.com/watch?v=bbbbbbbbbbb",
            "aaaaaaaaaaa",                       # duplicate of the first
        ])
        assert ids == ["aaaaaaaaaaa", "bbbbbbbbbbb"]
        assert skipped == []

    def test_reports_unparseable_entries(self):
        ids, skipped = yp.parse_video_list(["https://youtu.be/aaaaaaaaaaa", "garbage"])
        assert ids == ["aaaaaaaaaaa"]
        assert skipped == ["garbage"]

    def test_ignores_blank_lines_and_comments(self):
        ids, skipped = yp.parse_video_list([
            "# my favourites", "", "   ", "https://youtu.be/aaaaaaaaaaa",
        ])
        assert ids == ["aaaaaaaaaaa"]
        assert skipped == []


# ── Quota ────────────────────────────────────────────────────────────────────

class TestQuota:
    def test_playlist_plus_videos(self):
        # playlists.insert = 50, playlistItems.insert = 50 each
        assert yp.estimate_quota(n_videos=10) == 550

    def test_videos_only(self):
        assert yp.estimate_quota(n_videos=10, create_playlist=False) == 500

    def test_empty_playlist(self):
        assert yp.estimate_quota(n_videos=0) == 50

    def test_daily_limit_is_the_documented_default(self):
        assert yp.DAILY_QUOTA_DEFAULT == 10_000

    def test_max_videos_within_default_quota(self):
        # 50 + 50n <= 10000  ->  n <= 199
        assert yp.max_videos_for_quota(yp.DAILY_QUOTA_DEFAULT) == 199

    def test_over_budget_is_detected(self):
        assert yp.exceeds_quota(n_videos=200) is True
        assert yp.exceeds_quota(n_videos=199) is False


# ── Request bodies ───────────────────────────────────────────────────────────

class TestBodies:
    def test_playlist_body(self):
        body = yp.build_playlist_body("Titolo", "Descrizione", "unlisted")
        assert body["snippet"]["title"] == "Titolo"
        assert body["snippet"]["description"] == "Descrizione"
        assert body["status"]["privacyStatus"] == "unlisted"

    def test_playlist_item_body(self):
        body = yp.build_playlist_item_body("PL123", "vid123")
        assert body["snippet"]["playlistId"] == "PL123"
        assert body["snippet"]["resourceId"] == {"kind": "youtube#video", "videoId": "vid123"}

    @pytest.mark.parametrize("privacy", ["public", "unlisted", "private"])
    def test_valid_privacy_values(self, privacy):
        assert yp.build_playlist_body("t", "", privacy)["status"]["privacyStatus"] == privacy

    def test_invalid_privacy_rejected(self):
        with pytest.raises(ValueError, match="privacy"):
            yp.build_playlist_body("t", "", "semi-public")

    def test_empty_title_rejected(self):
        with pytest.raises(ValueError, match="title"):
            yp.build_playlist_body("   ", "", "private")

    def test_title_length_capped(self):
        # YouTube rejects titles over 150 chars; fail before spending quota
        with pytest.raises(ValueError, match="150"):
            yp.build_playlist_body("x" * 151, "", "private")


# ── Playlist creation ────────────────────────────────────────────────────────

class TestCreatePlaylist:
    def test_returns_id_and_url(self):
        fake = FakeYouTube(playlist_id="PLtest123")
        result = yp.create_playlist(fake, "Titolo", "Desc", "unlisted")
        assert result.playlist_id == "PLtest123"
        assert result.url == "https://www.youtube.com/playlist?list=PLtest123"

    def test_sends_snippet_and_status_parts(self):
        fake = FakeYouTube()
        yp.create_playlist(fake, "Titolo", "", "private")
        part, body = fake.playlist_bodies[0]
        assert set(part.split(",")) == {"snippet", "status"}
        assert body["snippet"]["title"] == "Titolo"

    def test_defaults_to_private(self):
        """An accidentally public playlist is not recoverable from the viewer's side."""
        fake = FakeYouTube()
        yp.create_playlist(fake, "Titolo")
        assert fake.playlist_bodies[0][1]["status"]["privacyStatus"] == "private"


# ── Adding videos ────────────────────────────────────────────────────────────

class TestAddVideos:
    def test_adds_each_video(self):
        fake = FakeYouTube()
        report = yp.add_videos(fake, "PL123", ["aaa", "bbb", "ccc"])
        assert report.added == ["aaa", "bbb", "ccc"]
        assert report.failed == []
        assert len(fake.item_bodies) == 3

    def test_one_bad_video_does_not_abort_the_batch(self):
        """A deleted or private video must not cost the whole run."""
        fake = FakeYouTube(item_errors={"bbb": RuntimeError("videoNotFound")})
        report = yp.add_videos(fake, "PL123", ["aaa", "bbb", "ccc"])
        assert report.added == ["aaa", "ccc"]
        assert [v for v, _ in report.failed] == ["bbb"]

    def test_failure_reason_is_kept(self):
        fake = FakeYouTube(item_errors={"aaa": RuntimeError("videoNotFound")})
        report = yp.add_videos(fake, "PL123", ["aaa"])
        assert "videoNotFound" in report.failed[0][1]

    def test_quota_spent_counts_only_attempts(self):
        fake = FakeYouTube(item_errors={"bbb": RuntimeError("boom")})
        report = yp.add_videos(fake, "PL123", ["aaa", "bbb"])
        assert report.quota_spent == 100      # both attempts cost 50

    def test_empty_list_is_a_no_op(self):
        fake = FakeYouTube()
        report = yp.add_videos(fake, "PL123", [])
        assert report.added == [] and report.quota_spent == 0
        assert fake.item_bodies == []

    def test_stops_at_quota_ceiling(self):
        fake = FakeYouTube()
        report = yp.add_videos(fake, "PL123", [f"v{i:08d}" for i in range(10)], quota_budget=200)
        assert len(report.added) == 4         # 200 / 50
        assert report.quota_exhausted is True
        assert len(report.skipped_for_quota) == 6
