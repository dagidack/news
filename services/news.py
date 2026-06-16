import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import feedparser
import httpx

from app.services.twitter_sources import MIRROR_WATCH_ACCOUNTS, PRIMARY_SOURCE_HANDLES
from app.services.video_probe import twitter_url_has_video

USER_AGENT = "BreakingNewsDesk/1.0 (journalist video aggregator)"

NITTER_MIRRORS = [
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
    "https://nitter.net",
]

ARTICLE_LINK_RE = re.compile(
    r"https?://(?!(?:www\.)?(?:x\.com|twitter\.com|t\.co|video\.twimg\.com))[^\s>]+",
    re.I,
)

ENTRIES_PER_ACCOUNT = 25
MAX_VIDEO_CHECKS = 80


@dataclass
class VideoItem:
    title: str
    url: str
    source: str
    published: str
    thumbnail: str | None = None
    description: str | None = None
    platform: str = "twitter"
    author_username: str | None = None
    author_name: str | None = None
    verified: bool = False
    is_primary_source: bool = False
    _published_dt: datetime | None = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "published": self.published,
            "thumbnail": self.thumbnail,
            "description": self.description,
            "platform": self.platform,
            "author": {
                "username": self.author_username,
                "name": self.author_name,
                "verified": self.verified,
            }
            if self.author_username
            else None,
            "is_primary_source": self.is_primary_source,
        }


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
    ):
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _iso(dt: datetime | None) -> str:
    if not dt:
        return ""
    return dt.isoformat()


def _is_primary_handle(username: str) -> bool:
    return username.lower().lstrip("@") in PRIMARY_SOURCE_HANDLES


def _is_retweet_text(text: str) -> bool:
    return bool(re.match(r"^RT\s+(@|by\s+@)", text.strip(), re.I))


def _tweet_passes_precheck(text: str) -> bool:
    if _is_retweet_text(text):
        return False
    if ARTICLE_LINK_RE.search(text):
        return False
    return True


def _normalize_x_url(link: str, username: str, tweet_id: str) -> str:
    if re.search(r"(x\.com|twitter\.com)/.+/status/", link, re.I):
        return re.sub(r"https?://[^/]+", "https://x.com", link)
    handle = username.lstrip("@")
    return f"https://x.com/{handle}/status/{tweet_id}"


def _dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for cand in candidates:
        if cand["tweet_id"] in seen:
            continue
        seen.add(cand["tweet_id"])
        unique.append(cand)
    return unique


async def _fetch_nitter_account(
    client: httpx.AsyncClient,
    mirror: str,
    username: str,
) -> list[dict[str, Any]]:
    url = f"{mirror}/{username}/rss"
    items: list[dict[str, Any]] = []
    try:
        resp = await client.get(url, headers={"User-Agent": USER_AGENT}, timeout=12.0)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
    except Exception:
        return items

    handle = username.lstrip("@")
    primary = _is_primary_handle(handle)

    for entry in feed.entries[:ENTRIES_PER_ACCOUNT]:
        title = entry.get("title", "")
        link = entry.get("link", "")
        if not _tweet_passes_precheck(title):
            continue

        tweet_id_match = re.search(r"/status/(\d+)", link)
        if not tweet_id_match:
            continue

        items.append(
            {
                "tweet_id": tweet_id_match.group(1),
                "text": title,
                "username": handle,
                "created_at": entry.get("published", ""),
                "url": _normalize_x_url(link, handle, tweet_id_match.group(1)),
                "primary": primary,
            }
        )

    return items


async def _fetch_from_mirrors(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    for mirror in NITTER_MIRRORS:
        tasks = [_fetch_nitter_account(client, mirror, account) for account in MIRROR_WATCH_ACCOUNTS]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, list):
                candidates.extend(result)
        if candidates:
            break

    return _dedupe_candidates(candidates)


def _build_item(cand: dict[str, Any]) -> VideoItem:
    dt = _parse_datetime(cand["created_at"])
    handle = cand["username"]
    return VideoItem(
        title=cand["text"][:280] or "Video post",
        url=cand["url"],
        source=f"X · @{handle}",
        published=_iso(dt),
        description=cand["text"][:300] if cand["text"] else None,
        platform="twitter",
        author_username=handle,
        author_name=handle,
        verified=True,
        is_primary_source=cand["primary"],
        _published_dt=dt,
    )


async def fetch_breaking_videos() -> dict[str, Any]:
    async with httpx.AsyncClient(follow_redirects=True) as client:
        candidates = await _fetch_from_mirrors(client)

    if not candidates:
        return {
            "count": 0,
            "twitter_count": 0,
            "source": "mirror",
            "mirror_accounts": len(MIRROR_WATCH_ACCOUNTS),
            "items": [],
        }

    to_check = candidates[:MAX_VIDEO_CHECKS]
    verified_flags = await asyncio.gather(
        *[twitter_url_has_video(c["url"]) for c in to_check],
        return_exceptions=True,
    )

    items: list[VideoItem] = []
    for cand, has_video in zip(to_check, verified_flags):
        if has_video is not True:
            continue
        items.append(_build_item(cand))

    # Primary sources first, then newest within each group (display only — no cutoff).
    items.sort(
        key=lambda x: (
            x.is_primary_source,
            x._published_dt or datetime.min.replace(tzinfo=timezone.utc),
        ),
        reverse=True,
    )

    return {
        "count": len(items),
        "twitter_count": len(items),
        "source": "mirror",
        "mirror_accounts": len(MIRROR_WATCH_ACCOUNTS),
        "items": [item.to_dict() for item in items],
    }
