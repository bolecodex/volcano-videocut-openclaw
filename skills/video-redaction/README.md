# Audit & Censorship Skill (Automated Pipeline)

This skill provides an end-to-end pipeline for auditing video content, detecting sensitive words (via LLM), censoring audio (beeping), and generating masked subtitles.

## 🚀 Quick Start

1.  **Setup Environment**
    ```bash
    bash scripts/setup.sh
    ```
    This will check for system dependencies (`node`, `ffmpeg`, `uv`) and install Python packages.

2.  **Configure API Keys**
    Edit `.env` file to add your LLM API keys (if using LLM detection).
    ```bash
    LLM_API_KEY=sk-xxxx
    LLM_BASE_URL=https://api.openai.com/v1
    ```

3.  **Run the Pipeline**
    ```bash
    python scripts/pipeline.py /path/to/video.mp4
    ```
    Output will be in `audit_output/` by default.

## 📂 Pipeline Overview

The `scripts/pipeline.py` orchestrates the following steps:

1.  **Audio Separation**: Uses `Demucs` to separate Vocals and Background Music.
2.  **ASR Transcription**: Uses `faster-whisper` (Local) to generate word-level transcription (`transcription.json`).
3.  **Sensitive Word Detection**:
    - Calls an LLM (OpenAI/Volcengine compatible) to identify sensitive content.
    - Fallback to keyword list if no API key is provided.
    - Outputs `sensitivity.json`.
4.  **Audio Censorship**: Replaces sensitive vocal segments with a beep sound (`asserts/dd6a0e.mp3`).
5.  **Subtitle Generation**: Generates `.ass` subtitles with sensitive words masked (`*`).
6.  **Final Merge**: Combines Video + Censored Vocals + BGM + Subtitles into `final_output.mp4`.

## 🛠 Scripts

- `scripts/pipeline.py`: Main entry point.
- `scripts/setup.sh`: Installation helper.
- `scripts/av_separation.sh`: Audio/Video separation logic.
- `scripts/asr_whisper.py`: Local ASR using faster-whisper.
- `scripts/detect_sensitive_words.py`: Detection logic (LLM/Keyword).
- `scripts/sensitive_audio_replace.py`: Audio processing for beeping.
- `scripts/generate_subtitles.py`: ASS subtitle generation.

## 📝 Configuration

- **Sensitive Words**: Detected via LLM prompt. You can customize the prompt in `detect_sensitive_words.py`.
- **Beep Sound**: Default is `asserts/dd6a0e.mp3`.
