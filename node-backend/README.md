# AI Video Transcriber (English & Tanglish)

A production-ready, dual-stack AI application that processes video files, extracts audio locally via FFmpeg, and uses advanced cloud LLMs to generate highly accurate `.srt` subtitles in either English or Romanized Tanglish.

## ✨ Features
* **Dual-Language Output:** Instantly translates Tamil video to English subtitles, or Romanizes Tamil script into Tanglish (English alphabet).
* **Modern UI/UX:** Features a sleek drag-and-drop interface, UI state locking during processing, and a graceful error-handling frontend.
* **100% Free AI Pipeline:** Utilizes Groq's generous free tier for both audio transcription (Whisper) and text reasoning (Llama 3.3), completely bypassing standard API rate limits.
* **Cloud-Accelerated:** Offloads heavy AI models to LPUs in the cloud, allowing the app to run instantly on any low-end local machine.

## 🏗️ Architecture
- **Frontend:** HTML, CSS, Vanilla JS (served via public static folder)
- **API Gateway:** Node.js + Express + Multer
- **AI Engine:** Python + FastAPI
- **Media Processing:** FFmpeg (Local CLI)
- **Transcription / Translation:** Groq API (`whisper-large-v3`)
- **Tanglish Transliteration:** Groq API (`llama-3.3-70b-versatile`)

## 📋 Prerequisites
1. **Node.js** installed (v18+)
2. **Python 3** installed (v3.10+)
3. **FFmpeg** installed and added to your system PATH (or `ffmpeg.exe` placed in the python directory)
4. A free API Key from [Groq Cloud](https://console.groq.com).

---

## 🚀 Setup Instructions

### 1. The Python AI Engine
Navigate to the Python directory and set up the virtual environment:

**Windows:**
```bash
cd python-ai-engine
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

```

**Mac/Linux:**

```bash
cd python-ai-engine
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

```

Create a `.env` file in the `python-ai-engine` folder and add your Groq key:

```text
GROQ_API_KEY=gsk_your_groq_api_key_here

```

Start the Python microservice:

```bash
python -m uvicorn main:app --reload --port 8000

```

### 2. The Node.js Gateway

In a **new terminal window**, navigate to the Node directory and install dependencies:

```bash
cd node-backend
npm install express multer axios form-data

```

Start the web server:

```bash
node server.js

```

---

## 💻 Usage

1. Open `http://localhost:3000` in your web browser.
2. Drag and drop a video file (`.mp4`, `.webm`, `.mkv`) into the upload zone.
3. Select your desired subtitle language output.
4. Click **Generate Subtitles** and wait for the file to process.
5. Click **Download Subtitles (.srt)** once processing is complete. If the AI transliteration fails, the UI will warn you and provide a fallback native-script file.

```