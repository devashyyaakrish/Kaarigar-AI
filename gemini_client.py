"""
Gemini AI Client — uses google-genai SDK (replaces deprecated google-generativeai).
Handles text, vision (image), and audio inputs with JSON parsing and fallbacks.
"""

import os
import json
import re
from dotenv import load_dotenv

load_dotenv()

API_KEY   = os.getenv("GEMINI_API_KEY", "")
MODEL_NAME = "gemini-2.5-flash"

_client    = None
_available = False


def _init():
    global _client, _available
    if _client is not None:
        return
    if not API_KEY:
        print("[gemini_client] WARNING — GEMINI_API_KEY not set. Using fallback responses.")
        _available = False
        return
    try:
        from google import genai
        _client = genai.Client(api_key=API_KEY)
        _available = True
        print(f"[gemini_client] Initialized model: {MODEL_NAME}")
    except Exception as e:
        print(f"[gemini_client] Failed to initialize: {e}")
        _available = False


def _extract_json(text: str):
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '',       text)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
    return None


def is_available() -> bool:
    _init()
    return _available


def generate_text(prompt: str) -> str:
    _init()
    if not _available:
        return ""
    try:
        from google import genai
        response = _client.models.generate_content(model=MODEL_NAME, contents=prompt)
        return response.text or ""
    except Exception as e:
        print(f"[gemini_client] generate_text error: {e}")
        return ""


def generate_json(prompt: str):
    raw = generate_text(prompt)
    return _extract_json(raw) if raw else None


def generate_with_image(prompt: str, image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
    _init()
    if not _available:
        return ""
    try:
        from google import genai
        from google.genai import types
        part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        response = _client.models.generate_content(
            model=MODEL_NAME,
            contents=[prompt, part]
        )
        return response.text or ""
    except Exception as e:
        print(f"[gemini_client] generate_with_image error: {e}")
        return ""


def generate_json_with_image(prompt: str, image_bytes: bytes, mime_type: str = "image/jpeg"):
    raw = generate_with_image(prompt, image_bytes, mime_type)
    return _extract_json(raw) if raw else None


def generate_with_two_images(prompt: str, img1_bytes: bytes, img2_bytes: bytes,
                               mime1: str = "image/jpeg", mime2: str = "image/jpeg") -> str:
    _init()
    if not _available:
        return ""
    try:
        from google import genai
        from google.genai import types
        part1 = types.Part.from_bytes(data=img1_bytes, mime_type=mime1)
        part2 = types.Part.from_bytes(data=img2_bytes, mime_type=mime2)
        response = _client.models.generate_content(
            model=MODEL_NAME,
            contents=[prompt, part1, part2]
        )
        return response.text or ""
    except Exception as e:
        print(f"[gemini_client] generate_with_two_images error: {e}")
        return ""


def generate_with_audio(prompt: str, audio_bytes: bytes, mime_type: str = "audio/webm") -> str:
    _init()
    if not _available:
        return ""
    try:
        from google import genai
        from google.genai import types
        part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
        response = _client.models.generate_content(
            model=MODEL_NAME,
            contents=[prompt, part]
        )
        return response.text or ""
    except Exception as e:
        print(f"[gemini_client] generate_with_audio error: {e}")
        return ""