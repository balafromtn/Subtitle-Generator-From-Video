# VDO → SRT — AI Tamil Subtitle Generator

A Streamlit application that turns Tamil videos into **English subtitles** or **Romanized Tanglish subtitles**. It uses FFmpeg for audio extraction, Groq Whisper for transcription/translation, and Groq Llama 3.3 for Tanglish transliteration.

## Features

- Upload MP4, WEBM and MKV videos.
- Generate English subtitles from Tamil speech.
- Generate Tanglish subtitles (Tamil words written with English letters).
- Validate a user-provided Groq API key before processing.
- Revalidate the key immediately before a job starts.
- Show useful errors for invalid credentials, rate limits, connection problems and processing failures.
- Preview and download the generated `.srt` file.
- Keep credentials in the user's Streamlit session; no key is committed to the repository.
- Clean up uploaded video and extracted audio files after processing.

## Architecture

```text
Streamlit UI (app.py)
  ├── User enters Groq API key
  ├── Authenticated key validation (Groq models.list)
  ├── Video upload / language selection / SRT preview & download
  └── Existing Python AI pipeline (python-ai-engine/pipeline.py)
        ├── FFmpeg audio extraction
        ├── Groq Whisper (whisper-large-v3)
        └── Groq Llama 3.3 (Tanglish only)
```

The original Node.js gateway is no longer required for the Streamlit deployment. The FastAPI service in `python-ai-engine/main.py` is retained as an optional standalone API for deployments that want to run the AI engine separately. The AI processing flow and model choices are preserved; the pipeline now receives a per-session Groq client instead of initializing cloud clients at import time.

## Run locally

### 1. Requirements

- Python 3.10+
- FFmpeg installed and available on `PATH`
- A Groq API key from [Groq Console](https://console.groq.com/keys)

### 2. Install dependencies

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
source .venv/bin/activate
```

Then:

```bash
pip install -r requirements.txt
```

### 3. Start Streamlit

```bash
streamlit run app.py
```

Open the local URL printed by Streamlit. Enter your own Groq API key in the UI, validate it, upload a video, choose Tanglish or English, and generate the SRT file.

## Optional FastAPI service

The FastAPI service remains available if you want a separate frontend or worker deployment:

```bash
cd python-ai-engine
uvicorn main:app --host 0.0.0.0 --port 8000
```

`POST /process-video` accepts multipart fields `video` and `language` (`english` or `tanglish`) and requires the `X-Groq-API-Key` request header. `GET /health` provides a basic health check.

## Security and privacy

- The UI does not persist the Groq key to disk or source control.
- The key is held in Streamlit's per-user session state and passed server-side to the Groq client.
- Do not paste API keys into issue trackers, screenshots or public logs.
- Uploaded videos and extracted audio are temporary and are cleaned up after processing. Generated subtitle text is held for the current interaction so it can be downloaded.
- Use HTTPS in production.

## Troubleshooting

| Message / symptom | What to check |
|---|---|
| Groq rejected the key | Create a new key in Groq Console and validate again. |
| Rate limit reached | Wait for the relevant Groq limit to reset, then retry. |
| Cannot connect to Groq | Check outbound network access and Groq service availability. |
| FFmpeg missing | Install FFmpeg and ensure `ffmpeg` is on `PATH`. |
| Failed to extract audio | Confirm the video is valid and contains an audio track. |
| No subtitle segments | Try a video with clearer speech or a supported audio track. |
| Tanglish fallback shown | Whisper succeeded, but the Llama transliteration call failed; the original Tamil SRT is retained as fallback. |

## Models used

- Transcription / English translation: `whisper-large-v3`
- Tanglish transliteration: `openai/gpt-oss-120b`

A single Groq API key and a per-session Groq client are reused for both models.
