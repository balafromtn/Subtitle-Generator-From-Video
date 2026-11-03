"""Optional FastAPI interface for deployments that run the AI engine separately."""

import os
import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.background import BackgroundTask
from groq import Groq, APIConnectionError, APIStatusError, AuthenticationError, RateLimitError

from pipeline import process_audio_pipeline

app = FastAPI(title="VDO to SRT AI Engine", version="2.0.0")


def _remove_file(path: str) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass


@app.get("/health")
async def health():
    return {"status": "ok", "service": "vdo-2-srt"}


@app.post("/process-video")
async def process_video(
    video: UploadFile = File(...),
    language: str = Form(...),
    x_groq_api_key: str = Header(..., alias="X-Groq-API-Key"),
):
    if language.lower() not in {"english", "tanglish"}:
        raise HTTPException(status_code=400, detail="Language must be English or Tanglish.")
    if not x_groq_api_key.strip().startswith("gsk_"):
        raise HTTPException(status_code=400, detail="A valid-format Groq API key is required.")

    client = Groq(api_key=x_groq_api_key.strip(), timeout=30.0, max_retries=0)
    try:
        client.models.list()
    except AuthenticationError:
        raise HTTPException(status_code=401, detail="Groq rejected the supplied API key.")
    except RateLimitError:
        raise HTTPException(status_code=429, detail="Groq rate-limited API-key validation. Try again shortly.")
    except APIConnectionError:
        raise HTTPException(status_code=503, detail="Could not connect to Groq for API-key validation.")
    except APIStatusError as exc:
        raise HTTPException(status_code=exc.status_code if 400 <= exc.status_code < 600 else 502,
                            detail=f"Groq validation failed (HTTP {exc.status_code}).")

    suffix = Path(video.filename or "video.mp4").suffix.lower()
    if suffix not in {".mp4", ".webm", ".mkv"}:
        raise HTTPException(status_code=400, detail="Supported video formats are MP4, WEBM and MKV.")

    work_dir = tempfile.mkdtemp(prefix="vdo2srt_api_")
    video_path = os.path.join(work_dir, f"{uuid.uuid4()}{suffix}")
    try:
        with open(video_path, "wb") as destination:
            shutil.copyfileobj(video.file, destination)
        srt_path = await process_audio_pipeline(video_path, language.lower(), groq_client=client)
        return FileResponse(
            path=srt_path,
            media_type="application/x-subrip",
            filename=f"transcript_{language.lower()}.srt",
            background=BackgroundTask(shutil.rmtree, work_dir, ignore_errors=True),
        )
    except HTTPException:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        await video.close()
