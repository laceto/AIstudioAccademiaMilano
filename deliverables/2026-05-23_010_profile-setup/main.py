"""
AI Studio Accademia Milano — Valentina: Profile Setup & Publishing Agent

Generates platform bios and first posts for all platforms, saves them to output/.
Optionally publishes to platforms with configured credentials.

Usage:
    python main.py --generate                    # generate all bios + first posts
    python main.py --generate --platform twitter_x  # one platform only
    python main.py --publish telegram            # publish saved post (asks for confirmation)
    python main.py --list                        # show all available platforms
"""
import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

OUTPUT_DIR = Path("output")


def cmd_list():
    from bio_generator import PLATFORM_SPECS
    from first_post_generator import PLATFORM_POST_SPECS
    from publisher import PUBLISHER_MAP, MANUAL_PLATFORMS

    print("\nBio platforms:")
    for p, spec in PLATFORM_SPECS.items():
        print(f"  {p:<28} max {spec['max_chars']} chars")

    print("\nFirst-post platforms:")
    for p, spec in PLATFORM_POST_SPECS.items():
        pub = "✅ auto-publish" if p in PUBLISHER_MAP else "✏️  manual"
        print(f"  {p:<28} {pub}  ({spec['limit']})")

    print("\nManual publishing instructions:")
    for p, instruction in MANUAL_PLATFORMS.items():
        print(f"  {p}: {instruction}")


def cmd_generate(args):
    from bio_generator import PLATFORM_SPECS, generate_bio
    from first_post_generator import PLATFORM_POST_SPECS, generate_first_post

    api_key = args.api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: set OPENAI_API_KEY or pass --api-key")
        sys.exit(1)

    OUTPUT_DIR.mkdir(exist_ok=True)

    bio_platforms = [args.platform] if args.platform and args.platform in PLATFORM_SPECS else (
        [] if args.platform else list(PLATFORM_SPECS)
    )
    post_platforms = [args.platform] if args.platform and args.platform in PLATFORM_POST_SPECS else (
        [] if args.platform else list(PLATFORM_POST_SPECS)
    )

    bios = {}
    if bio_platforms:
        print(f"\nGenerating {len(bio_platforms)} bio(s)...")
        for p in bio_platforms:
            print(f"  {p}", end=" ", flush=True)
            bios[p] = generate_bio(p, api_key)
            spec = PLATFORM_SPECS[p]
            over = len(bios[p]) - spec["max_chars"]
            status = f"⚠️ {over} over limit" if over > 0 else "done"
            print(status)
        (OUTPUT_DIR / "bios.json").write_text(json.dumps(bios, indent=2, ensure_ascii=False))
        md = ["# Platform Bios\n"]
        for p, bio in bios.items():
            spec = PLATFORM_SPECS[p]
            md.append(f"## {p.replace('_', ' ').title()} (max {spec['max_chars']} chars)\n")
            md.append(f"```\n{bio}\n```\n")
            md.append(f"*{len(bio)}/{spec['max_chars']} chars*\n")
        (OUTPUT_DIR / "bios.md").write_text("\n".join(md))
        print(f"  -> output/bios.md + output/bios.json")

    posts = {}
    if post_platforms:
        print(f"\nGenerating {len(post_platforms)} first post(s)...")
        for p in post_platforms:
            print(f"  {p}", end=" ", flush=True)
            posts[p] = generate_first_post(p, api_key)
            print("done")
        (OUTPUT_DIR / "first_posts.json").write_text(json.dumps(posts, indent=2, ensure_ascii=False))
        md = ["# First Posts\n"]
        for p, post in posts.items():
            md.append(f"## {p.replace('_', ' ').title()}\n")
            md.append(f"{post}\n")
            md.append("---\n")
        (OUTPUT_DIR / "first_posts.md").write_text("\n".join(md))
        print(f"  -> output/first_posts.md + output/first_posts.json")

    print("\nDone. Review output/ before publishing.")


def cmd_publish(args):
    from publisher import PUBLISHER_MAP, MANUAL_PLATFORMS

    platform = args.publish
    if platform in MANUAL_PLATFORMS:
        print(f"\n{platform}: manual posting required.")
        print(f"Instructions: {MANUAL_PLATFORMS[platform]}")
        posts_path = OUTPUT_DIR / "first_posts.json"
        if posts_path.exists():
            posts = json.loads(posts_path.read_text())
            if platform in posts:
                print(f"\nYour generated content:\n{'='*50}\n{posts[platform]}\n{'='*50}")
        return

    if platform not in PUBLISHER_MAP:
        print(f"Unknown platform '{platform}'. Run --list to see options.")
        sys.exit(1)

    posts_path = OUTPUT_DIR / "first_posts.json"
    if not posts_path.exists():
        print("Run --generate first.")
        sys.exit(1)

    posts = json.loads(posts_path.read_text())
    if platform not in posts:
        print(f"No post for '{platform}'. Run --generate --platform {platform} first.")
        sys.exit(1)

    text = posts[platform]
    print(f"\nPublishing to {platform}:\n{'='*50}\n{text}\n{'='*50}")
    if input("\nPublish? [y/N] ").strip().lower() != "y":
        print("Cancelled.")
        return

    try:
        result = PUBLISHER_MAP[platform](text)
        print(f"Published: {result}")
        log_path = OUTPUT_DIR / "publish_log.json"
        log = json.loads(log_path.read_text()) if log_path.exists() else []
        import datetime
        log.append({"platform": platform, "result": result, "ts": datetime.datetime.utcnow().isoformat()})
        log_path.write_text(json.dumps(log, indent=2))
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Valentina — Profile Setup & Publishing")
    parser.add_argument("--generate", action="store_true", help="Generate bios + first posts")
    parser.add_argument("--platform", help="Target a specific platform only")
    parser.add_argument("--publish", metavar="PLATFORM", help="Publish saved post to platform")
    parser.add_argument("--list", action="store_true", help="Show all platforms and their publish method")
    parser.add_argument("--api-key", help="OpenAI API key (or set OPENAI_API_KEY)")
    args = parser.parse_args()

    if args.list:
        cmd_list()
    elif args.generate:
        cmd_generate(args)
    elif args.publish:
        cmd_publish(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
