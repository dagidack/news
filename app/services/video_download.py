import asyncio
import tempfile
from pathlib import Path

from app.services.video_utils import is_video_url


async def download_video(url: str) -> tuple[Path, str]:
    if not is_video_url(url):
        raise ValueError("URL does not appear to be a supported video link.")

    import yt_dlp

    tmp_dir = Path(tempfile.mkdtemp(prefix="bnd_video_"))
    output_template = str(tmp_dir / "%(title).200B [%(id)s].%(ext)s")

    ydl_opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "max_filesize": 500 * 1024 * 1024,
    }

    def _run() -> tuple[Path, str]:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            path = Path(filename)
            if not path.exists():
                candidates = list(tmp_dir.glob("*"))
                if not candidates:
                    raise FileNotFoundError("Download completed but file was not found.")
                path = candidates[0]
            title = info.get("title", path.stem)
            return path, title

    return await asyncio.to_thread(_run)
