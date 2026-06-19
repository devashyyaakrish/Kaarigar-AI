"""
Pricing Engine — returns fair price ranges for home repair jobs in Jaipur.
Uses hardcoded base tables + optional Gemini calibration.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gemini_client import generate_json

# ---------------------------------------------------------------------------
# Base rate table (Jaipur market rates, INR)
# ---------------------------------------------------------------------------
BASE_RATES = {
    "plumbing": {
        "minor":    {"low": 200,  "mid": 400,  "high": 700},
        "moderate": {"low": 400,  "mid": 700,  "high": 1200},
        "severe":   {"low": 800,  "mid": 1500, "high": 3000},
    },
    "electrical": {
        "minor":    {"low": 200,  "mid": 350,  "high": 600},
        "moderate": {"low": 500,  "mid": 900,  "high": 1500},
        "severe":   {"low": 1000, "mid": 2000, "high": 4000},
    },
    "painting": {
        "minor":    {"low": 500,  "mid": 1000, "high": 2000},
        "moderate": {"low": 2000, "mid": 4000, "high": 8000},
        "severe":   {"low": 5000, "mid": 10000,"high": 20000},
    },
    "masonry": {
        "minor":    {"low": 500,  "mid": 1000, "high": 2000},
        "moderate": {"low": 1500, "mid": 3000, "high": 6000},
        "severe":   {"low": 3000, "mid": 6000, "high": 15000},
    },
    "carpentry": {
        "minor":    {"low": 300,  "mid": 600,  "high": 1200},
        "moderate": {"low": 800,  "mid": 1500, "high": 3000},
        "severe":   {"low": 2000, "mid": 4000, "high": 8000},
    },
    "ac_repair": {
        "minor":    {"low": 300,  "mid": 500,  "high": 1000},
        "moderate": {"low": 800,  "mid": 1500, "high": 3000},
        "severe":   {"low": 1500, "mid": 3000, "high": 6000},
    },
    "general": {
        "minor":    {"low": 200,  "mid": 400,  "high": 800},
        "moderate": {"low": 500,  "mid": 1000, "high": 2000},
        "severe":   {"low": 1000, "mid": 2000, "high": 5000},
    },
}

URGENCY_MULTIPLIERS = {
    "low": 0.9,
    "normal": 1.0,
    "urgent": 1.25,
    "emergency": 1.6,
}


def estimate_price(analysis: dict) -> dict:
    """
    Given an image/text analysis dict, return a price estimate dict.
    """
    problem_type = analysis.get("problem_type", "general")
    severity = analysis.get("severity", "moderate")
    urgency = analysis.get("urgency", "normal")

    rates = BASE_RATES.get(problem_type, BASE_RATES["general"])
    band = rates.get(severity, rates["moderate"])
    multiplier = URGENCY_MULTIPLIERS.get(urgency, 1.0)

    low  = int(band["low"]  * multiplier)
    mid  = int(band["mid"]  * multiplier)
    high = int(band["high"] * multiplier)

    return {
        "low":              low,
        "mid":              mid,
        "high":             high,
        "fair_single_quote": mid,
        "display":          f"₹{low} – ₹{high}",
        "breakdown": {
            "labour":    int(mid * 0.65),
            "materials": int(mid * 0.25),
            "travel":    int(mid * 0.10),
        },
        "problem_type": problem_type,
        "severity":     severity,
        "urgency":      urgency,
    }


def estimate_price_from_text(message: str) -> dict:
    """
    Estimate price from a free-text description (no image).
    Tries Gemini first, falls back to keyword-based detection.
    """
    prompt = f"""User is asking about home repair pricing in Jaipur, India.
Message: "{message}"

Identify the repair type and estimate a fair price range.
Return ONLY valid JSON:
{{
  "problem_type": "<plumbing|electrical|painting|masonry|carpentry|ac_repair|general>",
  "severity": "<minor|moderate|severe>",
  "urgency": "<low|normal|urgent|emergency>",
  "estimated_low": <INR number>,
  "estimated_mid": <INR number>,
  "estimated_high": <INR number>,
  "explanation_hindi": "<1-2 sentence Hindi/Hinglish explanation of why this price>"
}}"""

    result = generate_json(prompt)

    if result and isinstance(result, dict) and "estimated_mid" in result:
        mid  = result["estimated_mid"]
        low  = result.get("estimated_low", int(mid * 0.6))
        high = result.get("estimated_high", int(mid * 1.6))
        return {
            "low":              low,
            "mid":              mid,
            "high":             high,
            "fair_single_quote": mid,
            "display":          f"₹{low} – ₹{high}",
            "breakdown": {
                "labour":    int(mid * 0.65),
                "materials": int(mid * 0.25),
                "travel":    int(mid * 0.10),
            },
            "problem_type": result.get("problem_type", "general"),
            "severity":     result.get("severity", "moderate"),
            "urgency":      result.get("urgency", "normal"),
            "explanation":  result.get("explanation_hindi", ""),
        }

    # Keyword fallback
    analysis = _text_to_analysis(message)
    return estimate_price(analysis)


def _text_to_analysis(text: str) -> dict:
    tl = text.lower()
    problem_type = "general"
    for ptype, keywords in {
        "plumbing":   ["leak", "pipe", "drain", "tap", "water", "nal", "paani", "nali"],
        "electrical": ["electric", "wiring", "light", "fan", "switch", "bijli", "current"],
        "painting":   ["paint", "rang", "wall"],
        "masonry":    ["mason", "brick", "cement", "tile", "crack", "chhajja"],
        "carpentry":  ["door", "window", "furniture", "wood", "darwaza"],
        "ac_repair":  ["ac", "air condition", "cooling"],
    }.items():
        if any(k in tl for k in keywords):
            problem_type = ptype
            break

    urgency = "urgent" if any(u in tl for u in ["urgent", "jaldi", "emergency", "abhi"]) else "normal"
    severity = "severe" if any(s in tl for s in ["bahut", "zyada", "flood", "complete", "poora"]) else "moderate"

    return {"problem_type": problem_type, "severity": severity, "urgency": urgency}