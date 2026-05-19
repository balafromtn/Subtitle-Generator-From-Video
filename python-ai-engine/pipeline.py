import os
import subprocess
from dotenv import load_dotenv
from groq import Groq
import google.genai as genai

load_dotenv()
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
gemini_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

async def process_audio_pipeline(video_path: str, language: str) -> str:
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    audio_path = f"temp_processing/{base_name}.mp3"
    srt_path = f"temp_processing/{base_name}.srt"

    print("Extracting audio...")
    abs_video_path = os.path.abspath(video_path)
    abs_audio_path = os.path.abspath(audio_path)

    try:
        subprocess.run([
            "ffmpeg", "-i", abs_video_path, 
            "-vn", "-q:a", "0", abs_audio_path, "-y"
        ], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        raise Exception("Failed to extract audio. Make sure the video has an audio track!")

    # ---------------------------------------------------------
    # STEP 2: CLOUD TRANSCRIPTION / TRANSLATION
    # ---------------------------------------------------------
    if language.lower() == 'english':
        print("Translating audio directly to English via Groq...")
        with open(audio_path, "rb") as file:
            # Groq's built-in translation endpoint handles English natively
            api_response = groq_client.audio.translations.create(
                file=(audio_path, file.read()),
                model="whisper-large-v3",
                response_format="verbose_json"
            )
    else:
        print("Transcribing native audio via Groq...")
        with open(audio_path, "rb") as file:
            # Standard transcription gets the native language (Tamil)
            api_response = groq_client.audio.transcriptions.create(
                file=(audio_path, file.read()),
                model="whisper-large-v3",
                response_format="verbose_json"
            )

    # ---------------------------------------------------------
    # STEP 3: BUILD THE RAW SRT TEXT
    # ---------------------------------------------------------
    print("Formatting timestamps...")
    raw_srt_content = ""
    for index, segment in enumerate(api_response.segments, start=1):
        start_time = format_timestamp(segment["start"])
        end_time = format_timestamp(segment["end"])
        text = segment["text"].strip()
        
        raw_srt_content += f"{index}\n{start_time} --> {end_time}\n{text}\n\n"

    # ---------------------------------------------------------
    # STEP 4: BATCH TRANSLITERATION (TANGLISH ONLY)
    # ---------------------------------------------------------
    if language.lower() == 'tanglish':
        print("Sending full file to Gemini for Tanglish transliteration...")
        prompt = (
            "You are an expert at transliterating Tamil to Tanglish. "
            "I will give you a full SRT file written in Tamil script. "
            "You must TRANSLITERATE the entire text into Tanglish (Tamil words written using English letters). "
            "DO NOT translate the meaning into English. DO NOT leave a single Tamil letter behind. "
            "Use ONLY the standard English alphabet (a-z, A-Z), numbers, and punctuation.\n\n"
            "Example conversion:\n"
            "Input: வணக்கம், எப்படி இருக்கீங்க? இது ஒரு test.\n"
            "Output: Vanakkam, eppadi irukkinga? Ithu oru test.\n\n"
            "CRITICAL: You must keep the exact SRT formatting, line numbering, and timestamps intact.\n\n"
            f"Here is the file to transliterate:\n{raw_srt_content}"
        )
        
        try:
            # We ditched Gemini! Now using Groq's Llama-3.1-70B model for transliteration
            print("Sending text to Groq Llama 3 for Tanglish transliteration...")
            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a strict subtitle formatting bot. Only output the transliterated text. Do not add conversational filler."
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.1, # Keep it low so it doesn't get creative, just translates
            )
            
            # Extract the text from Groq's response
            response_text = chat_completion.choices[0].message.content
            final_srt_content = response_text.replace("```srt", "").replace("```", "").strip()
            
        except Exception as e:
            print(f"\n--- GROQ LLM CRASHED ---")
            print(f"Error details: {e}")
            print("------------------------\n")
            
            error_warning = "1\n00:00:00,000 --> 00:00:05,000\n[ERROR: GROQ TRANSLITERATION FAILED]\n\n"
            final_srt_content = error_warning + raw_srt_content
            
    else:
        final_srt_content = raw_srt_content

    # ---------------------------------------------------------
    # STEP 5: SAVE AND CLEANUP
    # ---------------------------------------------------------
    with open(srt_path, "w", encoding="utf-8") as srt_file:
        srt_file.write(final_srt_content)

    os.remove(video_path)
    os.remove(audio_path)

    print("Processing complete!")
    return srt_path

def format_timestamp(seconds: float) -> str:
    ms = int((seconds % 1) * 1000)
    s = int(seconds)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"