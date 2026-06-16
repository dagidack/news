# Breaking News Desk

A small desk tool for freelance journalists who repost trending news video on social media:

- **X video wire** — polls ~20 primary @handles (Reuters, AP, BBCBreaking, BNONews, Osinttechnical, etc.) via **public X mirrors**. No API key required. No date cutoff — whatever video posts appear in each account's RSS feed are shown.
- **Text tools** — paste a draft and turn it into a **headline** (brief overlay line), **shorten** it, or **rewrite** it.
- **Download video** — one-click download from X, YouTube, etc. via `yt-dlp`.

## Quick start

```bash
cd "/Users/d/Desktop/breaking news"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional: add OpenAI key for better text tools
./run.sh
```

Open [http://127.0.0.1:8080](http://127.0.0.1:8080).

## Optional configuration

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | Enables high-quality shorten/rewrite via GPT-4o mini. Without it, local algorithms are used. |

## How the X feed works

1. The app tries public mirror sites (nitter instances) to read RSS feeds for newsroom and OSINT accounts.
2. Retweets and article-link posts are skipped.
3. Each candidate tweet is checked for an actual video (`yt-dlp` probe).
4. Results are sorted with **primary sources first**, then by post date (newest first). There is **no freshness filter** — older videos in the feed are still shown.

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/news/videos` | GET | X video feed via mirrors |
| `/api/text/transform` | POST | `{ "text": "...", "mode": "headline" \| "shorten" \| "rewrite" }` |
| `/api/video/download` | POST | `{ "url": "https://..." }` — returns file |
| `/api/health` | GET | Service status |

## Notes

- Mirror availability varies; if one mirror is down the app tries the next.
- Video download depends on the host site and may fail for DRM-protected or login-gated content.
- Respect platform terms of service and copyright when downloading or republishing footage.
