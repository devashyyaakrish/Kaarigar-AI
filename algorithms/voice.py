"""
Voice Transcription — converts audio bytes to text using Gemini.
Falls back gracefully if audio processing fails.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gemini_client import generate_with_audio


def transcribe_voice(audio_bytes: bytes, mime_type: str = "audio/webm") -> str:
    """
    Transcribe a voice note (Hindi/Hinglish/English) to text.
    Returns the transcribed string, or a fallback message.
    """
    if not audio_bytes:
        return "[Empty audio]"

    prompt = """Transcribe this voice message accurately. 
The speaker may be speaking Hindi, Hinglish (Hindi-English mix), or English.
Return ONLY the transcription text — no labels, no explanation.
If you cannot hear clearly, transcribe your best guess."""

    try:
        result = generate_with_audio(prompt, audio_bytes, mime_type)
        if result and result.strip():
            return result.strip()
    except Exception as e:
        print(f"[voice] Transcription error: {e}")

    return "[Voice message — could not transcribe]"