"""
Check FAISS index freshness — AI Studio Accademia Milano.
Exits 1 with a warning if the index is older than --max-age-days (default 7).
Called by the embed_index_staleness_check hook.
"""

import argparse
import sys
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index-path", default="data/vectorstore/repo/index.faiss")
    parser.add_argument("--max-age-days", type=float, default=7.0)
    args = parser.parse_args()

    index = Path(args.index_path)
    if not index.exists():
        print(f"[check_index_freshness] Index not found: {index} — rebuild with: python -m scripts.embed_index")
        sys.exit(1)

    age_days = (time.time() - index.stat().st_mtime) / 86400
    if age_days > args.max_age_days:
        print(
            f"[check_index_freshness] Index is {age_days:.1f} days old (threshold: {args.max_age_days}d) — "
            f"rebuild with: python -m scripts.embed_index"
        )
        sys.exit(1)

    print(f"[check_index_freshness] Index age {age_days:.1f}d — OK.")


if __name__ == "__main__":
    main()
