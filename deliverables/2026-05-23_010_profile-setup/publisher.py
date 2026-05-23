"""
Publishing pipeline for AI Studio Accademia Milano.

Supported platforms (requires credentials per platform):
  twitter_x  — Tweepy v2 (TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_SECRET)
  telegram   — Bot API  (TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID)
  discord    — Webhook  (DISCORD_WEBHOOK_URL)
  reddit     — PRAW     (REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD)

LinkedIn and Instagram require manual posting (OAuth company-page flow is complex;
 use Deliverable 009 to generate the post text, then paste it manually).
"""
import os
from typing import Optional

import requests


def post_to_twitter(
    text: str,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    access_token: Optional[str] = None,
    access_secret: Optional[str] = None,
) -> dict:
    try:
        import tweepy
    except ImportError:
        raise ImportError("pip install tweepy>=4.14")
    client = tweepy.Client(
        consumer_key=api_key or os.environ["TWITTER_API_KEY"],
        consumer_secret=api_secret or os.environ["TWITTER_API_SECRET"],
        access_token=access_token or os.environ["TWITTER_ACCESS_TOKEN"],
        access_token_secret=access_secret or os.environ["TWITTER_ACCESS_SECRET"],
    )
    resp = client.create_tweet(text=text[:280])
    return {"id": resp.data["id"], "text": text[:280]}


def post_to_telegram(
    text: str,
    token: Optional[str] = None,
    channel_id: Optional[str] = None,
) -> dict:
    tok = token or os.environ["TELEGRAM_BOT_TOKEN"]
    cid = channel_id or os.environ["TELEGRAM_CHANNEL_ID"]
    r = requests.post(
        f"https://api.telegram.org/bot{tok}/sendMessage",
        json={"chat_id": cid, "text": text, "parse_mode": "Markdown"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def post_to_discord(text: str, webhook_url: Optional[str] = None) -> dict:
    url = webhook_url or os.environ["DISCORD_WEBHOOK_URL"]
    r = requests.post(url, json={"content": text}, timeout=10)
    r.raise_for_status()
    return {"status": "ok", "chars": len(text)}


def post_to_reddit(
    title: str,
    text: str,
    subreddit: str = "selfhosted",
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> dict:
    try:
        import praw
    except ImportError:
        raise ImportError("pip install praw>=7.7")
    reddit = praw.Reddit(
        client_id=client_id or os.environ["REDDIT_CLIENT_ID"],
        client_secret=client_secret or os.environ["REDDIT_CLIENT_SECRET"],
        username=username or os.environ["REDDIT_USERNAME"],
        password=password or os.environ["REDDIT_PASSWORD"],
        user_agent="AIStudioAccademiaMilano/1.0",
    )
    sub = reddit.subreddit(subreddit)
    submission = sub.submit(title=title, selftext=text)
    return {"id": submission.id, "url": submission.url}


PUBLISHER_MAP = {
    "twitter_x": post_to_twitter,
    "telegram": post_to_telegram,
    "discord": post_to_discord,
    "reddit": post_to_reddit,
}

MANUAL_PLATFORMS = {
    "linkedin": "Copy text from output/first_posts.md and paste at linkedin.com/feed/",
    "instagram": "Copy caption from output/first_posts.md, post with photo from your phone",
    "product_hunt": "Copy from output/first_posts.md, paste at producthunt.com/posts/new",
    "github_profile_readme": "Create repo <username>/<username>, paste output/first_posts.md content into README.md",
}
