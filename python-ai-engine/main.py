from fastapi import FastAPI, UploadFile, Form, File
from fastapi.responses import FileResponse
import shutil
import os
import uuid # <-- Add this import
from pipeline import process_audio_pipeline

app = FastAPI()

TEMP_DIR = "temp_processing"
os.makedirs(TEMP_DIR, exist_ok=True)

@app.post("/process-video")
async def process_video(
    video: UploadFile = File(...), 
    language: str = Form(...)
):
    # Grab the file extension (e.g., .webm, .mp4)
    file_ext = os.path.splitext(video.filename)[1]
    
    # Generate a perfectly safe, random filename (e.g., 550e8400-e29b.webm)
    safe_filename = f"{uuid.uuid4()}{file_ext}"
    video_path = os.path.join(TEMP_DIR, safe_filename)
    
    with open(video_path, "wb") as buffer:
        shutil.copyfileobj(video.file, buffer)
    
    srt_path = await process_audio_pipeline(video_path, language)
    
    return FileResponse(
        path=srt_path, 
        media_type='application/x-subrip', 
        filename=f"transcript_{language}.srt"
    )