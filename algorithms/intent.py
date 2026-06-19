"""
Intent Detection — classifies every incoming message into a structured intent.
Uses Gemini for NLU with a hardcoded fallback for demo reliability.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gemini_client import generate_json

# ---------------------------------------------------------------------------
# Keyword-based fast fallback (no API call needed)
# ---------------------------------------------------------------------------
_JOB_KEYWORDS = [
    "leak", "pipe", "plumb", "drain", "tap", "faucet", "water",
    "electric", "wiring", "light", "fan", "switch", "socket", "power",
    "paint", "wall", "crack", "ceiling",
    "mason", "brick", "cement", "tile", "floor",
    "carpenter", "door", "window", "furniture",
    "ac", "repair", "fix", "broken", "install", "nahi chal", "band ho",
    "problem", "issue", "kharab", "toot", "chhajja", "seepage",
]

_GREETING_KEYWORDS = ["hi", "hello", "helo", "namaste", "namaskar", "hey", "hii", "yo"]

_ACCEPT_KEYWORDS = ["haan", "yes", "ok", "okay", "theek", "manjoor", "accept", "send", "bhejo"]

_DECLINE_KEYWORDS = ["nahi", "nai", "no", "nope", "mat", "cancel", "decline", "band", "chodo"]

_PRICE_KEYWORDS = ["price", "kitna", "cost", "rate", "paisa", "rupee", "charge", "fees", "lagega"]

_JOB_TYPES = {
    "plumbing": ["leak", "pipe", "plumb", "drain", "tap", "faucet", "water", "nal", "paani", "seepage", "nali"],
    "electrical": ["electric", "wiring", "light", "fan", "switch", "socket", "power", "bijli", "current", "mcb", "fuse"],
    "painting": ["paint", "rang", "wall", "ceiling", "color"],
    "masonry": ["mason", "brick", "cement", "tile", "floor", "chhajja", "crack", "seepage", "deewar"],
    "carpentry": ["carpenter", "door", "window", "furniture", "wood", "darwaza", "khidki"],
    "ac_repair": ["ac", "air condition", "cooling", "heat pump", "inverter"],
    "general": [],
}


def _detect_job_type(text: str) -> str:
    tl = text.lower()
    for jtype, keywords in _JOB_TYPES.items():
        if any(k in tl for k in keywords):
            return jtype
    return "general"


def _detect_language(text: str) -> str:
    hindi_chars = sum(1 for c in text if '\u0900' <= c <= '\u097F')
    if hindi_chars > 3:
        return "hindi"
    hindi_words = ["karo", "karo", "hai", "hain", "nahi", "kya", "mujhe", "apna", "mere", "aap", "tum",
                   "bhai", "yaar", "accha", "theek", "thoda", "bahut", "abhi", "kal", "aaj"]
    tl = text.lower()
    if sum(1 for w in hindi_words if w in tl) >= 2:
        return "hinglish"
    return "english"


def _fast_intent(text: str) -> dict | None:
    """Quick keyword match — returns None if ambiguous."""
    tl = text.lower()

    # Single digit 1-3 → worker selection
    stripped = tl.strip()
    if stripped in ("1", "2", "3"):
        return {
            "intent": "worker_selection",
            "extracted": {"selection": int(stripped)},
            "language": _detect_language(text),
            "confidence": 0.95,
        }

    # 1-5 as decline reason when prefixed with nothing meaningful
    if stripped in ("4", "5"):
        return {
            "intent": "decline_reason",
            "extracted": {"reason_code": stripped},
            "language": _detect_language(text),
            "confidence": 0.90,
        }

    if any(k in tl for k in _GREETING_KEYWORDS) and len(tl.split()) <= 3:
        return {
            "intent": "greeting",
            "extracted": {},
            "language": _detect_language(text),
            "confidence": 0.95,
        }

    if any(k in tl for k in _ACCEPT_KEYWORDS) and len(tl.split()) <= 4:
        return {
            "intent": "job_accept",
            "extracted": {},
            "language": _detect_language(text),
            "confidence": 0.90,
        }

    if any(k in tl for k in _DECLINE_KEYWORDS) and len(tl.split()) <= 4:
        return {
            "intent": "job_decline",
            "extracted": {},
            "language": _detect_language(text),
            "confidence": 0.90,
        }

    if any(k in tl for k in _PRICE_KEYWORDS):
        return {
            "intent": "price_query",
            "extracted": {"job_type": _detect_job_type(text)},
            "language": _detect_language(text),
            "confidence": 0.85,
        }

    if any(k in tl for k in _JOB_KEYWORDS):
        return {
            "intent": "job_request",
            "extracted": {
                "job_type": _detect_job_type(text),
                "urgency": "urgent" if any(u in tl for u in ["urgent", "jaldi", "abhi", "emergency"]) else "normal",
            },
            "language": _detect_language(text),
            "confidence": 0.80,
        }

    return None


def detect_intent(message: str, history: list = None) -> dict:
    """
    Classify message intent. Tries fast keyword match first,
    falls back to Gemini if ambiguous.
    """
    # Fast path
    fast = _fast_intent(message)
    if fast and fast["confidence"] >= 0.85:
        return fast

    # Gemini path
    history_str = ""
    if history:
        last = history[-4:] if len(history) > 4 else history
        history_str = "\n".join(f"{h['role']}: {h['content']}" for h in last)

    prompt = f"""You are an intent classifier for a home-repair booking app in India.

Classify the user message into exactly ONE of these intents:
- greeting
- job_request       (user wants to book a repair)
- worker_selection  (user is picking worker 1/2/3)
- job_accept        (worker saying yes/haan/ok)
- job_decline       (worker saying nahi/no/cancel)
- decline_reason    (worker sending a number 1-5 as decline reason)
- price_query       (asking about cost/rate)
- completion_upload (worker saying job done / kaam ho gaya)
- general_question

Recent conversation:
{history_str}

Current message: "{message}"

Respond ONLY with valid JSON, no markdown:
{{
  "intent": "<one of the above>",
  "extracted": {{
    "job_type": "<plumbing|electrical|painting|masonry|carpentry|ac_repair|general if applicable>",
    "urgency": "<urgent|normal if applicable>",
    "selection": <1|2|3 if worker_selection>,
    "reason_code": "<1-5 if decline_reason>"
  }},
  "language": "<hindi|hinglish|english>",
  "confidence": <0.0-1.0>
}}"""

    result = generate_json(prompt)

    if result and isinstance(result, dict) and "intent" in result:
        return result

    # Final fallback — use fast result or default
    return fast or {
        "intent": "general_question",
        "extracted": {},
        "language": _detect_language(message),
        "confidence": 0.5,
    }