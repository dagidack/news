import re
from urllib.parse import urlparse

VIDEO_HOSTS = {
    "youtube.com",
    "youtu.be",
    "m.youtube.com",
    "twitter.com",
    "x.com",
    "mobile.twitter.com",
    "vimeo.com",
    "dailymotion.com",
    "dai.ly",
    "reddit.com",
    "v.redd.it",
    "streamable.com",
    "tiktok.com",
    "vm.tiktok.com",
    "facebook.com",
    "fb.watch",
    "instagram.com",
    "twitch.tv",
    "clips.twitch.tv",
    "rumble.com",
    "bitchute.com",
    "odysee.com",
    "liveleak.com",
    "apnews.com",
    "reuters.com",
    "bbc.com",
    "bbc.co.uk",
    "cnn.com",
    "nytimes.com",
    "theguardian.com",
}

VIDEO_PATH_HINTS = re.compile(
    r"/(video|videos|watch|reel|reels|status|clip|live|shorts)/",
    re.I,
)

VIDEO_EXTENSIONS = re.compile(r"\.(mp4|webm|m3u8|mov)(\?|$)", re.I)


def host_from_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower().removeprefix("www.")
        return host
    except Exception:
        return ""


def is_video_url(url: str) -> bool:
    if not url or not url.startswith(("http://", "https://")):
        return False

    host = host_from_url(url)
    if not host:
        return False

    if any(host == vh or host.endswith("." + vh) for vh in VIDEO_HOSTS):
        if host in {"reddit.com", "www.reddit.com"}:
            return "/r/" in url and ("/comments/" in url or "v.redd.it" in url)
        if host in {"facebook.com", "www.facebook.com", "instagram.com", "www.instagram.com"}:
            return bool(VIDEO_PATH_HINTS.search(url))
        return True

    if VIDEO_EXTENSIONS.search(url):
        return True

    if VIDEO_PATH_HINTS.search(url):
        return True

    return False


def normalize_source_label(url: str, fallback: str = "Web") -> str:
    host = host_from_url(url)
    labels = {
        "twitter.com": "X / Twitter",
        "x.com": "X / Twitter",
        "youtube.com": "YouTube",
        "youtu.be": "YouTube",
        "reddit.com": "Reddit",
        "v.redd.it": "Reddit",
        "vimeo.com": "Vimeo",
        "tiktok.com": "TikTok",
        "reuters.com": "Reuters",
        "bbc.com": "BBC",
        "bbc.co.uk": "BBC",
        "cnn.com": "CNN",
        "apnews.com": "AP",
    }
    for key, label in labels.items():
        if host == key or host.endswith("." + key):
            return label
    return fallback
