from __future__ import annotations

import asyncio
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import streamlit as st
from groq import Groq
from groq import APIConnectionError, APIStatusError, AuthenticationError, RateLimitError

ROOT_DIR = Path(__file__).resolve().parent
ENGINE_DIR = ROOT_DIR / "python-ai-engine"
sys.path.insert(0, str(ENGINE_DIR))
from pipeline import process_audio_pipeline  # noqa: E402

st.set_page_config(
    page_title="VDO → SRT | AI Subtitle Generator",
    page_icon="🎬",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .block-container {max-width: 900px; padding-top: 2.2rem; padding-bottom: 3rem;}
    .hero {text-align:center; padding: .6rem 0 1.2rem;}
    .hero h1 {font-size: clamp(2.2rem, 6vw, 3.2rem); letter-spacing:-1.5px; margin-bottom:.25rem;}
    .hero p {color: #9CA3AF; font-size:1.02rem;}
    .section-label {font-weight:650; margin: 1rem 0 .45rem;}
    div[data-testid="stFileUploader"] {border-radius:14px;}
    .small-note {color:#9CA3AF; font-size:.82rem;}
    </style>
    <div class="hero">
      <h1>🎬 VDO <span style="color:#8B9CF6">→</span> SRT</h1>
      <p>AI-powered Tamil video subtitle generator</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# Session-local credentials/client only. Never use a globally cached client:
# that could accidentally share one user's credentials with another user.
if "groq_client" not in st.session_state:
    st.session_state.groq_client = None
if "validated_key_fingerprint" not in st.session_state:
    st.session_state.validated_key_fingerprint = None
if "validation_message" not in st.session_state:
    st.session_state.validation_message = None
if "generated_srt" not in st.session_state:
    st.session_state.generated_srt = None
if "generated_filename" not in st.session_state:
    st.session_state.generated_filename = "transcript.srt"


def _fingerprint(value: str) -> str:
    # Used only to detect key changes in this session; the key itself is not logged.
    import hashlib
    return hashlib.sha256(value.encode("utf-8")).hexdigest() if value else ""


def _validate_groq_key(api_key: str) -> tuple[Groq | None, str | None]:
    if not api_key or not api_key.strip():
        return None, "Enter your Groq API key first."
    if not api_key.strip().startswith("gsk_"):
        return None, "This doesn't look like a Groq API key. Groq keys normally start with `gsk_`."
    try:
        client = Groq(api_key=api_key.strip(), timeout=20.0, max_retries=0)
        # Authenticated, lightweight request. Does not consume transcription/chat tokens.
        client.models.list()
        return client, None
    except AuthenticationError:
        return None, "Groq rejected this API key. Check that it is correct and active."
    except RateLimitError:
        return None, "Groq rate-limited the validation request. Wait a moment and try again."
    except APIConnectionError:
        return None, "Couldn't connect to Groq. Check your internet connection and try again."
    except APIStatusError as exc:
        if exc.status_code == 401:
            return None, "Groq rejected this API key. Check that it is correct and active."
        if exc.status_code == 403:
            return None, "Groq denied access to this key. Check its permissions or organization settings."
        if exc.status_code == 429:
            return None, "Groq rate-limited the validation request. Wait a moment and try again."
        return None, f"Groq validation failed (HTTP {exc.status_code}). Please try again later."
    except Exception:
        return None, "An unexpected error occurred while validating the key. Please try again."


def _key_changed() -> None:
    current = _fingerprint(st.session_state.get("groq_api_key_input", "").strip())
    if current != st.session_state.validated_key_fingerprint:
        st.session_state.groq_client = None
        st.session_state.validated_key_fingerprint = None
        st.session_state.validation_message = None


st.markdown("### 1. Connect your Groq API key")
st.caption("Your key is kept in this Streamlit session and is never written to project files.")
api_key = st.text_input(
    "Groq API key",
    type="password",
    placeholder="gsk_...",
    key="groq_api_key_input",
    help="Create a key at console.groq.com. Do not share your key with anyone.",
    on_change=_key_changed,
)

key_col, status_col = st.columns([1, 1.35], vertical_alignment="center")
with key_col:
    validate_clicked = st.button("Validate API key", type="primary", use_container_width=True)
with status_col:
    if st.session_state.groq_client is not None:
        st.success("API key validated", icon="✅")
    else:
        st.info("API key not validated", icon="🔐")

if validate_clicked:
    with st.spinner("Checking your Groq API key..."):
        client, error = _validate_groq_key(api_key.strip())
    if error:
        st.session_state.groq_client = None
        st.session_state.validated_key_fingerprint = None
        st.session_state.validation_message = error
        st.error(error)
    else:
        st.session_state.groq_client = client
        st.session_state.validated_key_fingerprint = _fingerprint(api_key.strip())
        st.session_state.validation_message = None
        st.success("Your Groq API key is valid. You're ready to generate subtitles!")

if st.session_state.validation_message and not validate_clicked:
    st.error(st.session_state.validation_message)

st.divider()
st.markdown("### 2. Upload your video")
st.caption("Supported formats: MP4, WEBM and MKV. Audio must be present in the video.")
video_file = st.file_uploader(
    "Choose a video file",
    type=["mp4", "webm", "mkv"],
    help="Maximum upload size is controlled by the hosting platform. The original interface allowed up to 500 MB.",
)

if video_file is not None:
    size_mb = len(video_file.getbuffer()) / (1024 * 1024)
    st.caption(f"**{video_file.name}** · {size_mb:.1f} MB")

st.markdown("### 3. Choose subtitle language")
language_label = st.radio(
    "Output language",
    options=["Tanglish", "English"],
    horizontal=True,
    help="Tanglish writes Tamil speech using English letters. English translates Tamil speech into English.",
    label_visibility="collapsed",
)

client_is_current = (
    st.session_state.groq_client is not None
    and st.session_state.validated_key_fingerprint == _fingerprint(api_key.strip())
)

if st.button(
    "✨ Generate subtitles",
    type="primary",
    use_container_width=True,
    disabled=(not client_is_current or video_file is None),
):
    if not shutil.which("ffmpeg"):
        st.error("FFmpeg is missing on this host. Install FFmpeg and make sure it is available on PATH.")
    else:
        st.session_state.generated_srt = None
        # Revalidate immediately before processing, as requested. This catches
        # revoked/expired credentials before spending time extracting audio.
        with st.spinner("Rechecking Groq credentials..."):
            fresh_client, validation_error = _validate_groq_key(api_key.strip())
        if validation_error:
            st.session_state.groq_client = None
            st.session_state.validated_key_fingerprint = None
            st.error(validation_error)
        else:
            st.session_state.groq_client = fresh_client
            suffix = Path(video_file.name).suffix.lower()
            try:
                with tempfile.TemporaryDirectory(prefix="vdo2srt_") as work_dir:
                    video_path = Path(work_dir) / f"uploaded_video{suffix}"
                    video_path.write_bytes(video_file.getvalue())
                    with st.status("Processing your video... This may take a few minutes.", expanded=False) as status:
                        srt_path = asyncio.run(
                            process_audio_pipeline(
                                str(video_path),
                                language_label.lower(),
                                groq_client=fresh_client,
                            )
                        )
                        srt_content = Path(srt_path).read_text(encoding="utf-8")
                        status.update(label="Subtitle generation complete", state="complete", expanded=False)

                safe_stem = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(video_file.name).stem).strip("_") or "transcript"
                st.session_state.generated_srt = srt_content
                st.session_state.generated_filename = f"{safe_stem}_{language_label.lower()}.srt"
            except AuthenticationError:
                st.session_state.groq_client = None
                st.session_state.validated_key_fingerprint = None
                st.error("Groq rejected the API key during processing. Please validate a current key and try again.")
            except RateLimitError:
                st.error("Groq rate limit reached. Wait before retrying. Your uploaded video has been cleaned up.")
            except APIConnectionError:
                st.error("Couldn't connect to Groq during processing. Check your connection and try again.")
            except Exception as exc:
                # Avoid displaying secrets or raw request headers in user-facing errors.
                message = str(exc)
                if api_key:
                    message = message.replace(api_key, "[REDACTED API KEY]")
                st.error(f"Processing failed: {message}")

if st.session_state.generated_srt:
    if "[ERROR: GROQ TRANSLITERATION FAILED" in st.session_state.generated_srt:
        st.warning("Transliteration could not be completed. Your original Tamil-script subtitles are available as a fallback.")
    else:
        st.success("Your subtitles are ready!")
    st.download_button(
        "⬇️ Download subtitles (.srt)",
        data=st.session_state.generated_srt.encode("utf-8"),
        file_name=st.session_state.generated_filename,
        mime="application/x-subrip",
        use_container_width=True,
        type="primary",
        on_click="ignore",
    )
    with st.expander("Preview subtitles"):
        st.code(st.session_state.generated_srt[:20000], language="text")
        if len(st.session_state.generated_srt) > 20000:
            st.caption("Preview truncated to the first 20,000 characters. Download the complete SRT above.")

st.divider()
st.markdown(
    '<p class="small-note">Your API key is session-scoped. Uploaded videos and extracted audio are stored temporarily for processing and cleaned up afterwards. Generated subtitles are available for download.</p>',
    unsafe_allow_html=True,
)
