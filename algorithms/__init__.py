from gemini_client import generate_json

def detect_intent(message: str, history: list) -> dict:
    prompt = f"""
You are an intent classifier for a home-repair WhatsApp bot in India.
Classify this message and return JSON only:
{{
  "intent": "greeting|job_request|worker_selection|price_query|job_accept|job_decline|decline_reason|completion_upload|general_question",
  "language": "hindi|english|hinglish",
  "extracted": {{
    "job_type": "plumbing|electrical|carpentry|painting|masonry|general",
    "urgency": "urgent|normal|low",
    "selection": null,
    "reason_code": null
  }}
}}

Message: "{message}"
"""
    result = generate_json(prompt)
    if not result:
        return {"intent": "general_question", "language": "hinglish", "extracted": {}}
    return result
