"""
Response Generator — creates natural WhatsApp-style messages for
customers (English/Hinglish) and workers (Hinglish/Hindi).
Uses Gemini for natural language generation with hardcoded fallbacks.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gemini_client import generate_text

# ---------------------------------------------------------------------------
# Hardcoded fallback templates (used when Gemini is unavailable)
# ---------------------------------------------------------------------------

def _worker_list_text(workers: list, price: dict) -> str:
    lines = []
    for i, w in enumerate(workers, 1):
        wk = w["worker"]
        lines.append(
            f"*{i}. {wk['name']}* ({wk.get('shop_name', '')})\n"
            f"   ⭐ {wk['trust_score']}/10 | ✅ {wk['jobs_completed']} jobs | "
            f"📍 {w['distance_km']}km | ⏱ ~{w['eta_minutes']} min"
        )
    return "\n".join(lines)


FALLBACKS = {
    "customer": {
        "greeting": (
            "Namaste! 🙏 Main Karigar AI hoon.\n"
            "Aapke ghar ka koi repair kaam hai? Batao ya photo bhejo — "
            "hum best worker dhundh denge! 🔧"
        ),
        "job_request": lambda ctx: (
            f"✅ *Repair Request Received!*\n\n"
            f"💰 *Estimated Cost:* {ctx.get('price_estimate', {}).get('display', 'TBD')}\n\n"
            f"👷 *Available Workers:*\n{_worker_list_text(ctx.get('matched_workers', []), ctx.get('price_estimate', {}))}\n\n"
            f"Kaun sa worker chahiye? *1, 2, ya 3* bhejo 📲"
        ),
        "price_query": lambda ctx: (
            f"💰 *Price Estimate for {ctx.get('price_estimate', {}).get('problem_type', 'your repair')}:*\n"
            f"Range: {ctx.get('price_estimate', {}).get('display', 'TBD')}\n"
            f"Fair rate: ₹{ctx.get('price_estimate', {}).get('fair_single_quote', 'TBD')}\n\n"
            f"Repair book karna hai? Problem describe karo! 🔧"
        ),
        "customer_worker_assigned": lambda ctx: (
            f"✅ *Worker Confirmed!*\n\n"
            f"👷 *{ctx.get('name', 'Worker')}* ({ctx.get('shop_name', '')})\n"
            f"⭐ Trust: {ctx.get('trust', 'N/A')}/10 | ✅ {ctx.get('jobs', 0)} jobs completed\n"
            f"📍 Distance: {ctx.get('distance', 'N/A')}km\n"
            f"⏱ ETA: ~{ctx.get('eta', 'N/A')} minutes\n\n"
            f"Worker raste mein hai! 🚗"
        ),
        "customer_worker_reassign": (
            "⏳ Worker unavailable, finding next best match...\n"
            "Thodi der mein update milega! 🔄"
        ),
    },
    "worker": {
        "greeting": (
            "Namaste bhai! 👋\n"
            "Main Karigar AI hoon — aapko nearby jobs milenge.\n"
            "Ready ho toh batao! 💪"
        ),
        "job_request": lambda ctx: (
            f"🔔 *Naya Kaam Available!*\n\n"
            f"📋 {ctx.get('job_description_hindi', 'Repair work')}\n"
            f"📍 Distance: ~{ctx.get('distance', 'N/A')}km\n"
            f"💰 Expected Pay: ₹{ctx.get('expected_pay', 'TBD')}\n\n"
            f"Accept karo? *Haan* ya *Nahi* bhejo 📲"
        ),
        "worker_accept": lambda ctx: (
            f"✅ Bahut badhiya {ctx.get('name', 'bhai')}!\n\n"
            f"📍 Customer ke paas jao: {ctx.get('area', 'Customer area')}\n"
            f"💰 Expected pay: ₹{ctx.get('expected_pay', 'TBD')}\n\n"
            f"Kaam khatam hone par photo bhejo verification ke liye 📸"
        ),
        "decline_survey": lambda ctx: (
            f"Theek hai {ctx.get('name', 'bhai')}! 🙏\n\n"
            f"Decline ka reason batao (number bhejo):\n"
            f"1️⃣ Abhi busy hoon\n"
            f"2️⃣ Bahut door hai\n"
            f"3️⃣ Yeh skill nahi hai\n"
            f"4️⃣ Rate kam hai\n"
            f"5️⃣ Personal reason"
        ),
        "job_completed": lambda ctx: (
            f"✅ {ctx.get('feedback', 'Kaam verified! 👍')}\n\n"
            f"Customer ko rating dene ka intezaar karo ⭐"
        ),
    }
}


def generate_response(
    response_type: str,
    context: dict,
    language: str = "english",
    role: str = "customer",
) -> str:
    """
    Generate a WhatsApp-style response message.

    Args:
        response_type: Type of response (greeting, job_request, worker_accept, etc.)
        context: Data to fill into the template
        language: hindi | hinglish | english
        role: customer | worker
    """
    # Try Gemini first for natural responses
    gemini_result = _try_gemini(response_type, context, language, role)
    if gemini_result:
        return gemini_result

    # Fallback to hardcoded templates
    return _get_fallback(response_type, context, role)


def _try_gemini(response_type: str, context: dict, language: str, role: str) -> str:
    """Ask Gemini to generate a natural WhatsApp message."""
    lang_instruction = {
        "hindi":    "Write in Hindi (Devanagari script ok, but Roman Hindi preferred for WhatsApp)",
        "hinglish": "Write in Hinglish (Hindi-English mix, casual WhatsApp style)",
        "english":  "Write in simple English suitable for Indian WhatsApp users",
    }.get(language, "Write in simple English")

    # Build context summary
    ctx_str = ""
    if response_type == "job_request" and role == "customer":
        workers = context.get("matched_workers", [])
        price = context.get("price_estimate", {})
        analysis = context.get("problem_analysis", {})
        ctx_str = (
            f"Problem: {analysis.get('specific_issue', 'repair needed')}\n"
            f"Severity: {analysis.get('severity', 'moderate')}\n"
            f"Price range: {price.get('display', 'TBD')}\n"
            f"Workers found: {len(workers)}\n"
        )
        for i, w in enumerate(workers, 1):
            wk = w["worker"]
            ctx_str += f"Worker {i}: {wk['name']} — {wk['trust_score']}/10 trust — {w['distance_km']}km — {w['eta_minutes']} min ETA\n"

    elif response_type == "job_request" and role == "worker":
        ctx_str = (
            f"Job description (Hindi): {context.get('job_description_hindi', '')}\n"
            f"Distance: {context.get('distance', 'N/A')}km\n"
            f"Expected pay: ₹{context.get('expected_pay', 'TBD')}\n"
        )

    elif response_type in ("worker_accept", "customer_worker_assigned"):
        ctx_str = str(context)

    elif response_type == "decline_survey":
        ctx_str = f"Worker name: {context.get('name', 'Bhai')}"

    elif response_type == "price_query":
        price = context.get("price_estimate", {})
        ctx_str = f"Price range: {price.get('display', 'TBD')}, Fair rate: ₹{price.get('fair_single_quote', 'TBD')}"

    prompt = f"""You are Karigar AI — a WhatsApp chatbot for home repair booking in India (Jaipur).
{lang_instruction}.

Generate a WhatsApp message of type: {response_type}
Role sending to: {role}

Context:
{ctx_str}

Rules:
- Keep it concise (max 150 words)
- Use WhatsApp formatting (*bold*, emojis)
- Sound like a friendly, helpful assistant
- For job_request to customer: list workers with numbers 1/2/3 for selection
- For job_request to worker: ask them to reply Haan/Nahi
- For decline_survey: list exactly 5 numbered reasons
- Return ONLY the message text, no quotes or labels"""

    try:
        result = generate_text(prompt)
        if result and len(result) > 10:
            return result.strip()
    except Exception as e:
        print(f"[response_gen] Gemini failed: {e}")

    return ""


def _get_fallback(response_type: str, context: dict, role: str) -> str:
    """Get hardcoded fallback template."""
    templates = FALLBACKS.get(role, FALLBACKS["customer"])
    template = templates.get(response_type, templates.get("greeting", "Namaste! 🙏"))

    if callable(template):
        try:
            return template(context)
        except Exception:
            return "Namaste! 🙏 Karigar AI mein aapka swagat hai!"

    return template