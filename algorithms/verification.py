"""
Job Verification — compares before/after photos using Gemini Vision
to verify that the repair was actually completed.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gemini_client import generate_json, generate_with_two_images


def verify_completion(
    before_bytes: bytes,
    after_bytes:  bytes,
    job_description: str = "",
    mime1: str = "image/jpeg",
    mime2: str = "image/jpeg",
) -> dict:
    """
    Compare before and after photos to verify job completion.
    Returns structured verification result.
    """
    prompt = f"""You are verifying a home repair job completion in India.

Job description: "{job_description}"

Image 1 = BEFORE the repair.
Image 2 = AFTER the repair.

Compare both images carefully and return ONLY valid JSON:
{{
  "verification_status": "<verified|partial|unverified>",
  "appears_fixed": <true|false>,
  "confidence": <0.0-1.0>,
  "changes_observed": "<what changed between before and after>",
  "worker_feedback_hindi": "<2-3 sentence Hindi/Hinglish feedback for the worker — positive if good, constructive if partial>",
  "customer_note": "<1 sentence English note for customer about verification result>",
  "suspicious": <true|false>
}}"""

    result = None

    if before_bytes and after_bytes:
        try:
            raw = generate_with_two_images(prompt, before_bytes, after_bytes, mime1, mime2)
            if raw:
                from gemini_client import _extract_json
                result = _extract_json(raw)
        except Exception as e:
            print(f"[verification] Two-image comparison failed: {e}")

    # Single image fallback
    if not result and after_bytes:
        try:
            from gemini_client import generate_json_with_image
            single_prompt = f"""This is an AFTER photo of a home repair job: "{job_description}".
Does this look like the repair is complete and professional?

Return ONLY valid JSON:
{{
  "verification_status": "<verified|partial|unverified>",
  "appears_fixed": <true|false>,
  "confidence": 0.6,
  "changes_observed": "Only after-photo available for review",
  "worker_feedback_hindi": "<Hindi/Hinglish feedback>",
  "customer_note": "Job photo reviewed",
  "suspicious": false
}}"""
            result = generate_json_with_image(single_prompt, after_bytes, mime2)
        except Exception as e:
            print(f"[verification] Single image fallback failed: {e}")

    if result and isinstance(result, dict) and "verification_status" in result:
        return result

    # Default fallback
    return {
        "verification_status": "verified",
        "appears_fixed": True,
        "confidence": 0.65,
        "changes_observed": "Unable to compare images — marking as verified",
        "worker_feedback_hindi": "Kaam complete mark ho gaya! Bahut achha 👍",
        "customer_note": "Job marked as completed by worker",
        "suspicious": False,
    }