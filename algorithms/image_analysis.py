"""
Image Analysis — uses Gemini Vision to identify repair problem type,
severity, materials, and generates a Hindi summary for the worker ping.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gemini_client import generate_json_with_image, generate_json


def analyze_problem_image(image_bytes: bytes, caption: str = "", mime_type: str = "image/jpeg") -> dict:
    """
    Analyze a customer's problem photo.
    Returns a structured dict with problem_type, severity, price hints, etc.
    """
    prompt = f"""You are an expert home repair AI assistant working in India (Jaipur, Rajasthan).

Analyze this image of a home repair problem. Caption from customer: "{caption}"

Return ONLY valid JSON (no markdown, no explanation):
{{
  "problem_type": "<plumbing|electrical|painting|masonry|carpentry|ac_repair|general>",
  "specific_issue": "<one clear English sentence describing the exact problem>",
  "hindi_summary": "<2-3 sentence Hindi/Hinglish description for the worker, casual tone>",
  "severity": "<minor|moderate|severe>",
  "urgency": "<low|normal|urgent|emergency>",
  "diy_possible": <true|false>,
  "estimated_time_hours": <number>,
  "materials_likely_needed": ["<material1>", "<material2>"],
  "confidence": <0.0-1.0>
}}"""

    result = None
    if image_bytes:
        result = generate_json_with_image(prompt, image_bytes, mime_type)

    if result and isinstance(result, dict) and "problem_type" in result:
        return result

    # Text-only fallback if image analysis fails
    if caption:
        return _analyze_from_caption(caption)

    return _default_analysis()


def _analyze_from_caption(caption: str) -> dict:
    """Fallback: analyze from caption text only."""
    prompt = f"""Home repair problem description from customer in India: "{caption}"

Return ONLY valid JSON:
{{
  "problem_type": "<plumbing|electrical|painting|masonry|carpentry|ac_repair|general>",
  "specific_issue": "<one clear English sentence>",
  "hindi_summary": "<2-3 sentence Hindi/Hinglish description for worker>",
  "severity": "<minor|moderate|severe>",
  "urgency": "<low|normal|urgent|emergency>",
  "diy_possible": false,
  "estimated_time_hours": 2,
  "materials_likely_needed": ["Will assess on site"],
  "confidence": 0.6
}}"""
    result = generate_json(prompt)
    if result and isinstance(result, dict):
        return result
    return _default_analysis()


def _default_analysis() -> dict:
    return {
        "problem_type": "general",
        "specific_issue": "Home repair issue requiring professional assessment",
        "hindi_summary": "Ghar mein koi repair ka kaam hai. Site par jaake assess karna hoga.",
        "severity": "moderate",
        "urgency": "normal",
        "diy_possible": False,
        "estimated_time_hours": 2,
        "materials_likely_needed": ["Will assess on site"],
        "confidence": 0.4,
    }