import shutil
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, HttpUrl

from app.config import settings
from app.services.news import fetch_breaking_videos
from app.services.text_tools import Mode, transform_text
from app.services.video_download import download_video

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Breaking News Desk", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TextRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=20000)
    mode: Mode


class DownloadRequest(BaseModel):
    url: HttpUrl


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "source": "mirror",
        "openai_configured": bool(settings.openai_api_key),
    }


@app.get("/api/news/videos")
async def get_video_news():
    try:
        return await fetch_breaking_videos()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch video news: {exc}") from exc


@app.post("/api/text/transform")
async def text_transform(body: TextRequest):
    try:
        return await transform_text(body.text, body.mode)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Text transform failed: {exc}") from exc


@app.post("/api/video/download")
async def video_download(body: DownloadRequest):
    url = str(body.url)
    try:
        path, title = await download_video(url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Video download failed: {exc}") from exc

    safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)[:120]
    filename = f"{safe_name}{path.suffix or '.mp4'}"

    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=filename,
        background=lambda: shutil.rmtree(path.parent, ignore_errors=True),
    )


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
