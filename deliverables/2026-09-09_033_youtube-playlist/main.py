"""
main.py — CLI for D033: create a YouTube playlist from a list of videos.

    # preview: parse, dedupe, price the run — no API calls, no OAuth
    python main.py --title "AI Studio — Research" --from-file videos.txt --dry-run

    # for real
    python main.py --title "AI Studio — Research" --from-file videos.txt

    # public, with a description, from arguments
    python main.py --title "Demo" --privacy public --description "Studio demos" \
        https://youtu.be/aaaaaaaaaaa https://www.youtube.com/watch?v=bbbbbbbbbbb

Input accepts full URLs (watch, youtu.be, shorts, embed) or bare 11-char IDs.
In a file, blank lines and `#` comments are ignored.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import youtube_playlist as yp


def _read_entries(args) -> list[str]:
    entries = list(args.videos)
    if args.from_file:
        path = Path(args.from_file)
        if not path.exists():
            sys.exit(f"ERROR: file not found: {path}")
        entries += path.read_text(encoding="utf-8").splitlines()
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a YouTube playlist and fill it with videos.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("videos", nargs="*", help="Video URLs or IDs")
    parser.add_argument("--title", required=True, help="Playlist title (max 150 chars)")
    parser.add_argument("--description", default="", help="Playlist description")
    parser.add_argument("--privacy", default="private", choices=yp.VALID_PRIVACY,
                        help="Default: private")
    parser.add_argument("--from-file", help="Text file with one URL or ID per line")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse and price the run without calling the API")
    parser.add_argument("--quota-budget", type=int, default=yp.DAILY_QUOTA_DEFAULT,
                        help=f"Units available today (default {yp.DAILY_QUOTA_DEFAULT})")
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt")
    args = parser.parse_args()

    entries = _read_entries(args)
    if not entries:
        sys.exit("ERROR: no videos given — pass URLs or use --from-file.")

    video_ids, skipped = yp.parse_video_list(entries)

    # Fail on a bad title now, not after spending 50 units creating nothing.
    try:
        yp.build_playlist_body(args.title, args.description, args.privacy)
    except ValueError as exc:
        sys.exit(f"ERROR: {exc}")

    print(f"Playlist : {args.title}  [{args.privacy}]")
    print(f"Videos   : {len(video_ids)} unique")
    if skipped:
        print(f"Skipped  : {len(skipped)} unparseable entr"
              f"{'y' if len(skipped) == 1 else 'ies'}")
        for entry in skipped[:10]:
            print(f"           - {entry[:70]}")
        if len(skipped) > 10:
            print(f"           ... and {len(skipped) - 10} more")

    cost = yp.estimate_quota(len(video_ids))
    print(f"Quota    : {cost} of {args.quota_budget} units "
          f"(50 create + 50 x {len(video_ids)})")

    if cost > args.quota_budget:
        fits = yp.max_videos_for_quota(args.quota_budget)
        print(f"\nWARNING: over budget. Only the first {fits} video(s) will be added; "
              f"the rest need tomorrow's quota or a quota increase.")

    if args.dry_run:
        print("\nDry run — nothing was created.")
        return 0

    if not args.yes:
        try:
            if input("\nProceed? [y/N] ").strip().lower() not in {"y", "yes"}:
                print("Aborted.")
                return 1
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            return 1

    service = yp.get_service()

    playlist = yp.create_playlist(service, args.title, args.description, args.privacy)
    print(f"\nCreated: {playlist.url}")

    remaining = args.quota_budget - playlist.quota_spent
    report = yp.add_videos(service, playlist.playlist_id, video_ids,
                           quota_budget=remaining)

    print(f"Added   : {len(report.added)}")
    if report.failed:
        print(f"Failed  : {len(report.failed)}")
        for video_id, reason in report.failed:
            print(f"          - {video_id}: {reason[:90]}")
    if report.quota_exhausted:
        print(f"Quota exhausted — {len(report.skipped_for_quota)} video(s) not added:")
        for video_id in report.skipped_for_quota[:10]:
            print(f"          - https://youtu.be/{video_id}")
        print("Re-run tomorrow with --from-file listing the remainder.")

    print(f"Spent   : {playlist.quota_spent + report.quota_spent} units")
    print(f"\n{playlist.url}")
    return 0 if not report.failed else 2


if __name__ == "__main__":
    sys.exit(main())
