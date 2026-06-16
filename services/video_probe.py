import asyncio
import contextlib
import io


async def twitter_url_has_video(url: str) -> bool:
    """Check whether an X status URL resolves to downloadable video footage."""

    def _probe() -> bool:
        import yt_dlp

        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
            "logger": None,
        }
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)
        except Exception:
            return False

        if not info:
            return False
        if info.get("vcodec") and info.get("vcodec") != "none":
            return True
        if info.get("url") and str(info.get("url", "")).endswith((".mp4", ".m3u8")):
            return True
        return bool(info.get("formats"))

    return await asyncio.to_thread(_probe)
