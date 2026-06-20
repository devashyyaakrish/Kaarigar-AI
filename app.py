"""
Karigar AI — Flask Backend
Central orchestrator: receives messages from the dual-pane UI,
routes through AI algorithms, and returns responses for both panes.
"""

import os
import json
import base64
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory

# Algorithm imports
from algorithms.intent import detect_intent
from algorithms.voice import transcribe_voice
from algorithms.image_analysis import analyze_problem_image
from algorithms.pricing import estimate_price, estimate_price_from_text
from algorithms.matching import (
    find_best_workers, load_worker, save_worker, update_worker_after_review,
    DEFAULT_CUSTOMER_LAT, DEFAULT_CUSTOMER_LON
)
from algorithms.verification import verify_completion
from algorithms.response_gen import generate_response
import re

# ---------------------------------------------------------------------------
# Flask app setup
# ---------------------------------------------------------------------------
app = Flask(__name__, static_folder='frontend', static_url_path='')

# ---------------------------------------------------------------------------
# In-memory session store (demo — no real DB needed)
# ---------------------------------------------------------------------------
SESSION = {
    "customer": {
        "history": [],
        "language": "english",
        "lat": DEFAULT_CUSTOMER_LAT,
        "lon": DEFAULT_CUSTOMER_LON,
    },
    "worker": {
        "history": [],
        "language": "hinglish",
    },
    "current_job": None,           # active job being processed
    "matched_workers": [],         # top 3 from last match
    "selected_worker": None,       # the worker chosen by customer
    "excluded_workers": [],        # workers who declined this job
    "before_image": None,          # customer's problem image (bytes)
    "before_image_b64": None,      # base64 for frontend display
    "problem_analysis": None,      # result of image/text analysis
    "price_estimate": None,        # result of pricing engine
    "awaiting_decline_reason": False,
    "awaiting_worker_selection": False,
    "awaiting_completion": False,
    "pending_customer_confirmation": False,
    "awaiting_rating": False,
}

def _reset_session():
    """Reset session to clean state."""
    SESSION["customer"]["history"] = []
    SESSION["worker"]["history"] = []
    SESSION["current_job"] = None
    SESSION["matched_workers"] = []
    SESSION["selected_worker"] = None
    SESSION["excluded_workers"] = []
    SESSION["before_image"] = None
    SESSION["before_image_b64"] = None
    SESSION["problem_analysis"] = None
    SESSION["price_estimate"] = None
    SESSION["awaiting_decline_reason"] = False
    SESSION["awaiting_worker_selection"] = False
    SESSION["awaiting_completion"] = False
    SESSION["pending_customer_confirmation"] = False
    SESSION["awaiting_rating"] = False

# ---------------------------------------------------------------------------
# Routes — Static files
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    return send_from_directory('frontend', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('frontend', path)

# ---------------------------------------------------------------------------
# Routes — API
# ---------------------------------------------------------------------------
@app.route('/api/reset', methods=['POST'])
def reset():
    """Reset the demo to a clean state."""
    _reset_session()
    return jsonify({"status": "reset", "message": "Demo reset to clean state"})

@app.route('/api/session', methods=['GET'])
def get_session():
    """Get current session state (for debugging)."""
    safe = {k: v for k, v in SESSION.items() if k not in ('before_image',)}
    return jsonify(safe)

# ---------------------------------------------------------------------------
# Customer message handler
# ---------------------------------------------------------------------------
@app.route('/api/customer/message', methods=['POST'])
def customer_message():
    """Handle a text message from the customer pane."""
    data = request.json
    message = data.get('message', '').strip()
    if not message:
        return jsonify({"error": "Empty message"}), 400

    # Add to history
    SESSION["customer"]["history"].append({
        "role": "user", "content": message, "timestamp": _now()
    })

    # --- State-based routing (priority over intent detection) ---

    # Awaiting rating?
    if SESSION["awaiting_rating"]:
        return _handle_customer_rating(message)

    if SESSION.get("pending_customer_confirmation"):
        return _handle_customer_confirmation(message)

    # Awaiting worker selection (customer picks 1/2/3)?
    if SESSION["awaiting_worker_selection"]:
        return _handle_worker_selection(message)

    # --- Intent detection ---
    intent_result = detect_intent(message, SESSION["customer"]["history"])
    intent = intent_result.get("intent", "general_question")
    SESSION["customer"]["language"] = intent_result.get("language", "english")

    if intent == "greeting":
        reply = generate_response("greeting", {}, SESSION["customer"]["language"], "customer")
        SESSION["customer"]["history"].append({"role": "assistant", "content": reply, "timestamp": _now()})
        return jsonify({"customer_reply": reply, "worker_reply": None})

    elif intent == "job_request":
        return _handle_job_request_text(message, intent_result)

    elif intent == "worker_selection":
        selection = intent_result.get("extracted", {}).get("selection")
        if selection:
            return _handle_worker_selection(str(selection))

    elif intent == "price_query":
        price = estimate_price_from_text(message)
        reply = generate_response("price_query", {
            "price_estimate": price,
            "original_message": message,
            "city": "Jaipur"
        }, SESSION["customer"]["language"], "customer")
        SESSION["customer"]["history"].append({"role": "assistant", "content": reply, "timestamp": _now()})
        return jsonify({"customer_reply": reply, "worker_reply": None})

    else:
        # General conversation
        reply = generate_response("greeting", {}, SESSION["customer"]["language"], "customer")
        SESSION["customer"]["history"].append({"role": "assistant", "content": reply, "timestamp": _now()})
        return jsonify({"customer_reply": reply, "worker_reply": None})


@app.route('/api/customer/image', methods=['POST'])
def customer_image():
    """Handle an image upload from the customer pane."""
    text = request.form.get('message', '')

    if 'image' not in request.files:
        return jsonify({"error": "No image provided"}), 400

    file = request.files['image']
    image_bytes = file.read()
    mime_type = file.content_type or 'image/jpeg'

    # Store the before image
    SESSION["before_image"] = image_bytes
    SESSION["before_image_b64"] = base64.b64encode(image_bytes).decode('utf-8')

    SESSION["customer"]["history"].append({
        "role": "user", "content": f"[Photo uploaded] {text}", "timestamp": _now()
    })

    # Analyze the image
    analysis = analyze_problem_image(image_bytes, text, mime_type)
    SESSION["problem_analysis"] = analysis

    # Get price estimate
    price = estimate_price(analysis)
    SESSION["price_estimate"] = price

    # Find best workers
    workers = find_best_workers(
        SESSION["customer"]["lat"],
        SESSION["customer"]["lon"],
        analysis.get("problem_type", "plumbing"),
        exclude_ids=SESSION["excluded_workers"]
    )
    SESSION["matched_workers"] = workers

    if not workers:
        reply = "Sorry, abhi koi worker available nahi hai aapke area mein 🙏"
        SESSION["customer"]["history"].append({"role": "assistant", "content": reply, "timestamp": _now()})
        return jsonify({"customer_reply": reply, "worker_reply": None})

    # Generate customer response
    reply = generate_response("job_request", {
        "matched_workers": workers,
        "price_estimate": price,
        "problem_analysis": analysis
    }, SESSION["customer"]["language"], "customer")

    SESSION["customer"]["history"].append({"role": "assistant", "content": reply, "timestamp": _now()})
    SESSION["awaiting_worker_selection"] = True

    # Create job record
    SESSION["current_job"] = {
        "id": f"job_{_now_ts()}",
        "problem_type": analysis.get("problem_type"),
        "description": analysis.get("specific_issue"),
        "hindi_description": analysis.get("hindi_summary"),
        "severity": analysis.get("severity"),
        "price_estimate": price,
        "status": "awaiting_selection",
        "created_at": _now()
    }

    return jsonify({
        "customer_reply": reply,
        "worker_reply": None,
        "analysis": analysis,
        "price_estimate": price,
        "workers_found": len(workers)
    })


@app.route('/api/customer/voice', methods=['POST'])
def customer_voice():
    """Handle a voice message from the customer pane."""
    if 'audio' not in request.files:
        return jsonify({"error": "No audio provided"}), 400

    file = request.files['audio']
    audio_bytes = file.read()
    mime_type = file.content_type or 'audio/webm'

    # Transcribe
    transcript = transcribe_voice(audio_bytes, mime_type)

    # Process as text message
    SESSION["customer"]["history"].append({
        "role": "user", "content": f"🎤 {transcript}", "timestamp": _now()
    })

    # Re-run through text handler logic
    intent_result = detect_intent(transcript, SESSION["customer"]["history"])
    intent = intent_result.get("intent", "general_question")

    if intent == "job_request":
        return _handle_job_request_text(transcript, intent_result, is_voice=True)
    elif intent == "price_query":
        price = estimate_price_from_text(transcript)
        reply = generate_response("price_query", {
            "price_estimate": price,
            "original_message": transcript,
            "city": "Jaipur"
        }, SESSION["customer"]["language"], "customer")
        SESSION["customer"]["history"].append({"role": "assistant", "content": reply, "timestamp": _now()})
        return jsonify({"customer_reply": reply, "worker_reply": None, "transcript": transcript})
    else:
        reply = generate_response("greeting", {}, SESSION["customer"]["language"], "customer")
        SESSION["customer"]["history"].append({"role": "assistant", "content": reply, "timestamp": _now()})
        return jsonify({"customer_reply": reply, "worker_reply": None, "transcript": transcript})


# ---------------------------------------------------------------------------
# Worker message handler
# ---------------------------------------------------------------------------
@app.route('/api/worker/message', methods=['POST'])
def worker_message():
    """Handle a text message from the worker pane."""
    data = request.json
    message = data.get('message', '').strip()
    if not message:
        return jsonify({"error": "Empty message"}), 400

    SESSION["worker"]["history"].append({
        "role": "user", "content": message, "timestamp": _now()
    })

    # --- State-based routing ---

    # Awaiting decline reason (1-5)?
    if SESSION["awaiting_decline_reason"]:
        return _handle_decline_reason(message)

    # --- Intent detection ---
    intent_result = detect_intent(message, SESSION["worker"]["history"])
    intent = intent_result.get("intent", "general_question")
    SESSION["worker"]["language"] = intent_result.get("language", "hinglish")

    if intent == "greeting":
        reply = generate_response("greeting", {}, SESSION["worker"]["language"], "worker")
        SESSION["worker"]["history"].append({"role": "assistant", "content": reply, "timestamp": _now()})
        return jsonify({"worker_reply": reply, "customer_reply": None})

    elif intent == "job_accept":
        return _handle_worker_accept()

    elif intent == "job_decline":
        return _handle_worker_decline()

    elif intent == "decline_reason":
        reason = intent_result.get("extracted", {}).get("reason_code")
        if reason:
            return _handle_decline_reason(reason)

    elif intent == "completion_upload":
        SESSION["awaiting_completion"] = True
        reply = "Photo bhejo kaam ka — before/after dono 📸"
        SESSION["worker"]["history"].append({"role": "assistant", "content": reply, "timestamp": _now()})
        return jsonify({"worker_reply": reply, "customer_reply": None})

    elif intent == "price_query":
        price = estimate_price_from_text(message)
        reply = generate_response("price_query", {
            "price_estimate": price,
            "original_message": message,
            "city": "Jaipur"
        }, SESSION["worker"]["language"], "worker")
        SESSION["worker"]["history"].append({"role": "assistant", "content": reply, "timestamp": _now()})
        return jsonify({"worker_reply": reply, "customer_reply": None})

    else:
        reply = generate_response("greeting", {}, SESSION["worker"]["language"], "worker")
        SESSION["worker"]["history"].append({"role": "assistant", "content": reply, "timestamp": _now()})
        return jsonify({"worker_reply": reply, "customer_reply": None})


@app.route('/api/worker/image', methods=['POST'])
def worker_image():
    """Handle an image upload from the worker (completion photo)."""
    if 'image' not in request.files:
        return jsonify({"error": "No image provided"}), 400

    file = request.files['image']
    after_image = file.read()
    mime_type = file.content_type or 'image/jpeg'

    after_b64 = base64.b64encode(after_image).decode('utf-8')

    SESSION["worker"]["history"].append({
        "role": "user", "content": "[Completion photo uploaded]", "timestamp": _now()
    })

    # Verify completion
    before_image = SESSION.get("before_image")
    job_desc = ""
    if SESSION.get("problem_analysis"):
        job_desc = SESSION["problem_analysis"].get("specific_issue", "")

    if before_image:
        verification = verify_completion(before_image, after_image, job_desc, "image/jpeg", mime_type)
    else:
        verification = {
            "verification_status": "verified",
            "confidence": 0.7,
            "worker_feedback_hindi": "Kaam complete mark ho gaya! 👍",
            "appears_fixed": True,
            "suspicious": False
        }

    # Worker response
    worker_reply = generate_response("job_completed", {
        "feedback": verification.get("worker_feedback_hindi", "Kaam verified! 👍")
    }, SESSION["worker"]["language"], "worker")

    SESSION["worker"]["history"].append({"role": "assistant", "content": worker_reply, "timestamp": _now()})

    status = verification.get("verification_status", "verified")
    if status == "verified":
        customer_msg = f"""✅ *Job Completed & Verified!*

The repair work has been verified by our AI system.
Verification confidence: {int(verification.get('confidence', 0.8) * 100)}%

Worker ko 1 se 5 mein rate karo (5 = best).
Bas number bhejo, chaaho to ek line feedback bhi likh do."""
        SESSION["awaiting_rating"] = True
    else:
        customer_msg = """⚠️ *Job Completed*

Worker ne kaam complete bataya hai. Kya yeh sahi se fix ho gaya? (Haan/Nahi)"""
        SESSION["pending_customer_confirmation"] = True

    SESSION["customer"]["history"].append({"role": "assistant", "content": customer_msg, "timestamp": _now()})
    SESSION["awaiting_completion"] = False

    return jsonify({
        "worker_reply": worker_reply,
        "customer_reply": customer_msg,
        "verification": verification,
        "after_image_b64": after_b64
    })


@app.route('/api/worker/voice', methods=['POST'])
def worker_voice():
    """Handle a voice message from the worker pane."""
    if 'audio' not in request.files:
        return jsonify({"error": "No audio provided"}), 400

    file = request.files['audio']
    audio_bytes = file.read()
    mime_type = file.content_type or 'audio/webm'

    # Transcribe
    transcript = transcribe_voice(audio_bytes, mime_type)

    SESSION["worker"]["history"].append({
        "role": "user", "content": f"🎤 {transcript}", "timestamp": _now()
    })

    # Process as text
    intent_result = detect_intent(transcript, SESSION["worker"]["history"])
    intent = intent_result.get("intent", "general_question")

    if intent == "price_query":
        price = estimate_price_from_text(transcript)
        reply = generate_response("price_query", {
            "price_estimate": price,
            "original_message": transcript,
            "city": "Jaipur"
        }, SESSION["worker"]["language"], "worker")
        SESSION["worker"]["history"].append({"role": "assistant", "content": reply, "timestamp": _now()})
        return jsonify({"worker_reply": reply, "customer_reply": None, "transcript": transcript})

    elif intent == "job_accept":
        return _handle_worker_accept()

    elif intent == "job_decline":
        return _handle_worker_decline()

    else:
        reply = generate_response("greeting", {}, SESSION["worker"]["language"], "worker")
        SESSION["worker"]["history"].append({"role": "assistant", "content": reply, "timestamp": _now()})
        return jsonify({"worker_reply": reply, "customer_reply": None, "transcript": transcript})


# ---------------------------------------------------------------------------
# Internal flow handlers
# ---------------------------------------------------------------------------

def _handle_job_request_text(message: str, intent_result: dict, is_voice: bool = False):
    """Handle a text-based job request (no image)."""
    job_type = intent_result.get("extracted", {}).get("job_type", "plumbing")

    # Create a synthetic analysis from text
    analysis = {
        "problem_type": job_type,
        "specific_issue": message,
        "severity": "moderate",
        "urgency": intent_result.get("extracted", {}).get("urgency", "normal"),
        "diy_possible": False,
        "estimated_time_hours": 2,
        "materials_likely_needed": ["Will be determined on site"],
        "confidence": 0.6,
        "hindi_summary": message  # pass through for now; AI will handle translation
    }
    SESSION["problem_analysis"] = analysis

    # Get price estimate
    price = estimate_price(analysis)
    SESSION["price_estimate"] = price

    # Find workers
    workers = find_best_workers(
        SESSION["customer"]["lat"],
        SESSION["customer"]["lon"],
        job_type,
        exclude_ids=SESSION["excluded_workers"]
    )
    SESSION["matched_workers"] = workers

    if not workers:
        reply = "Sorry, abhi koi worker available nahi hai is kaam ke liye. Thodi der baad try karein 🙏"
        SESSION["customer"]["history"].append({"role": "assistant", "content": reply, "timestamp": _now()})
        return jsonify({"customer_reply": reply, "worker_reply": None})

    # Generate response
    reply = generate_response("job_request", {
        "matched_workers": workers,
        "price_estimate": price,
        "problem_analysis": analysis
    }, SESSION["customer"]["language"], "customer")

    SESSION["customer"]["history"].append({"role": "assistant", "content": reply, "timestamp": _now()})
    SESSION["awaiting_worker_selection"] = True

    SESSION["current_job"] = {
        "id": f"job_{_now_ts()}",
        "problem_type": job_type,
        "description": message,
        "hindi_description": analysis.get("hindi_summary", message),
        "severity": "moderate",
        "price_estimate": price,
        "status": "awaiting_selection",
        "created_at": _now()
    }

    return jsonify({
        "customer_reply": reply,
        "worker_reply": None,
        "analysis": analysis,
        "price_estimate": price,
        "workers_found": len(workers)
    })


def _handle_worker_selection(selection_text: str):
    """Customer selected a worker (1, 2, 3, etc.)."""
    workers = SESSION.get("matched_workers", [])
    max_options = len(workers)
    
    match = re.search(r'\d+', selection_text)
    if not match:
        reply = f"Please send a number between 1 and {max_options} to select a worker 🙏"
        SESSION["customer"]["history"].append({"role": "assistant", "content": reply, "timestamp": _now()})
        return jsonify({"customer_reply": reply, "worker_reply": None})
        
    idx = int(match.group()) - 1

    if idx < 0 or idx >= max_options:
        reply = f"Please send a number between 1 and {max_options} 🙏"
        SESSION["customer"]["history"].append({"role": "assistant", "content": reply, "timestamp": _now()})
        return jsonify({"customer_reply": reply, "worker_reply": None})

    selected = workers[idx]
    SESSION["selected_worker"] = selected
    SESSION["awaiting_worker_selection"] = False

    # Customer confirmation
    customer_reply = f"✅ Sending your request to *{selected['worker']['name']}*...\nPlease wait for their response ⏳"
    SESSION["customer"]["history"].append({"role": "assistant", "content": customer_reply, "timestamp": _now()})

    # Worker ping
    price = SESSION.get("price_estimate", {})
    analysis = SESSION.get("problem_analysis", {})

    worker_reply = generate_response("job_request", {
        "job_description_hindi": analysis.get("hindi_summary", analysis.get("specific_issue", "Repair work")),
        "distance": selected['distance_km'],
        "expected_pay": price.get('fair_single_quote', 800),
        "area_name": "Customer area"
    }, "hinglish", "worker")

    SESSION["worker"]["history"].append({"role": "assistant", "content": worker_reply, "timestamp": _now()})

    if SESSION.get("current_job"):
        SESSION["current_job"]["status"] = "awaiting_worker_response"
        SESSION["current_job"]["selected_worker_id"] = selected['worker']['id']

    return jsonify({
        "customer_reply": customer_reply,
        "worker_reply": worker_reply,
        "selected_worker": {
            "name": selected['worker']['name'],
            "distance": selected['distance_km'],
            "eta": selected['eta_minutes'],
            "trust": selected['worker']['trust_score']
        }
    })


def _handle_worker_accept():
    """Worker accepted the job."""
    selected = SESSION.get("selected_worker")
    if not selected:
        reply = "Abhi koi pending kaam nahi hai bhai 🙏"
        SESSION["worker"]["history"].append({"role": "assistant", "content": reply, "timestamp": _now()})
        return jsonify({"worker_reply": reply, "customer_reply": None})

    worker = selected['worker']
    price = SESSION.get("price_estimate", {})
    analysis = SESSION.get("problem_analysis", {})

    # Worker confirmation
    worker_reply = generate_response("worker_accept", {
        "name": worker['name'],
        "area": "Customer area",
        "job_desc": analysis.get('hindi_summary', analysis.get('specific_issue', 'Repair work')),
        "expected_pay": price.get('fair_single_quote', 800)
    }, "hinglish", "worker")

    SESSION["worker"]["history"].append({"role": "assistant", "content": worker_reply, "timestamp": _now()})

    # Customer notification
    customer_reply = generate_response("customer_worker_assigned", {
        "name": worker['name'],
        "shop_name": worker.get('shop_name', ''),
        "distance": selected['distance_km'],
        "eta": selected['eta_minutes'],
        "trust": worker['trust_score'],
        "jobs": worker.get('jobs_completed', 0)
    }, SESSION["customer"]["language"], "customer")

    SESSION["customer"]["history"].append({"role": "assistant", "content": customer_reply, "timestamp": _now()})

    if SESSION.get("current_job"):
        SESSION["current_job"]["status"] = "in_progress"

    SESSION["awaiting_completion"] = True

    return jsonify({
        "worker_reply": worker_reply,
        "customer_reply": customer_reply
    })


def _handle_worker_decline():
    """Worker declined the job — send the 5-option micro-survey."""
    selected = SESSION.get("selected_worker")
    name = selected['worker']['name'] if selected else "Bhai"

    # Send decline survey
    worker_reply = generate_response("decline_survey", {
        "name": name.split()[0]  # first name only
    }, "hinglish", "worker")

    SESSION["worker"]["history"].append({"role": "assistant", "content": worker_reply, "timestamp": _now()})
    SESSION["awaiting_decline_reason"] = True

    # Notify customer
    customer_reply = generate_response("customer_worker_reassign", {}, SESSION["customer"]["language"], "customer")
    SESSION["customer"]["history"].append({"role": "assistant", "content": customer_reply, "timestamp": _now()})

    return jsonify({
        "worker_reply": worker_reply,
        "customer_reply": customer_reply
    })


def _handle_decline_reason(reason_text: str):
    """Process the decline reason and reassign the job."""
    try:
        reason_code = str(int(reason_text.strip()))
    except (ValueError, TypeError):
        reply = "Sirf number bhejo (1-5) 🙏"
        SESSION["worker"]["history"].append({"role": "assistant", "content": reply, "timestamp": _now()})
        return jsonify({"worker_reply": reply, "customer_reply": None})

    if reason_code not in ["1", "2", "3", "4", "5"]:
        reply = "1 se 5 ke beech mein number bhejo 🙏"
        SESSION["worker"]["history"].append({"role": "assistant", "content": reply, "timestamp": _now()})
        return jsonify({"worker_reply": reply, "customer_reply": None})

    SESSION["awaiting_decline_reason"] = False

    # Process the decline — update worker profile
    selected = SESSION.get("selected_worker")
    if selected:
        worker_data = selected['worker']
        _process_decline(worker_data, reason_code)

        # Add to excluded list
        SESSION["excluded_workers"].append(worker_data['id'])

    # Acknowledge to worker
    reason_labels = {
        "1": "Busy",
        "2": "Too far",
        "3": "Wrong skill",
        "4": "Low rate",
        "5": "Personal"
    }
    worker_reply = f"Theek hai bhai, samajh gaya 👍\n({reason_labels.get(reason_code, 'Noted')})"
    SESSION["worker"]["history"].append({"role": "assistant", "content": worker_reply, "timestamp": _now()})

    # Reassign to next worker
    analysis = SESSION.get("problem_analysis", {})
    job_type = analysis.get("problem_type", "plumbing")

    new_workers = find_best_workers(
        SESSION["customer"]["lat"],
        SESSION["customer"]["lon"],
        job_type,
        exclude_ids=SESSION["excluded_workers"]
    )

    if new_workers:
        next_worker = new_workers[0]
        SESSION["selected_worker"] = next_worker
        SESSION["matched_workers"] = new_workers

        price = SESSION.get("price_estimate", {})

        # New worker ping
        new_worker_reply = generate_response("job_request", {
            "job_description_hindi": analysis.get("hindi_summary", analysis.get("specific_issue", "Repair work")),
            "distance": next_worker['distance_km'],
            "expected_pay": price.get('fair_single_quote', 800),
            "area_name": "Customer area"
        }, "hinglish", "worker")

        # Add a separator then the new ping
        separator = f"\n--- Naya worker: {next_worker['worker']['name']} ---\n"
        SESSION["worker"]["history"].append({"role": "assistant", "content": separator + new_worker_reply, "timestamp": _now()})

        # Customer update
        customer_reply = f"🔄 *New worker found:*\n👷 {next_worker['worker']['name']} — {next_worker['distance_km']}km — Trust: {next_worker['worker']['trust_score']}/10\n\nRequest sent! ⏳"
        SESSION["customer"]["history"].append({"role": "assistant", "content": customer_reply, "timestamp": _now()})

        if SESSION.get("current_job"):
            SESSION["current_job"]["selected_worker_id"] = next_worker['worker']['id']

        return jsonify({
            "worker_reply": worker_reply + "\n\n" + separator + new_worker_reply,
            "customer_reply": customer_reply,
            "reassigned_to": next_worker['worker']['name'],
            "decline_processed": True,
            "reason_code": reason_code
        })
    else:
        customer_reply = "Sorry, abhi aur koi worker available nahi hai. Thodi der baad try karein 🙏"
        SESSION["customer"]["history"].append({"role": "assistant", "content": customer_reply, "timestamp": _now()})
        return jsonify({
            "worker_reply": worker_reply,
            "customer_reply": customer_reply,
            "reassigned_to": None,
            "decline_processed": True,
            "reason_code": reason_code
        })


def _handle_customer_rating(message: str):
    """Handle customer rating (1-5) and feedback."""
    match = re.search(r'[1-5]', message)
    if not match:
        reply = "Bas 1 se 5 ke beech ek number bhejo 🙏"
        SESSION["customer"]["history"].append({"role": "assistant", "content": reply, "timestamp": _now()})
        return jsonify({"customer_reply": reply, "worker_reply": None})

    rating = int(match.group())
    feedback_text = message.replace(match.group(), '', 1).strip() or None

    SESSION["awaiting_rating"] = False

    selected = SESSION.get("selected_worker")
    if selected:
        worker_id = selected['worker']['id']
        job = SESSION.get("current_job", {})
        job['rating'] = rating
        job['review_text'] = feedback_text
        job['status'] = 'closed'
        job['customer_phone'] = "+910000000000"
        
        update_worker_after_review(worker_id, rating, job)

    stars = "⭐" * rating
    reply = f"""Dhanyawad! Aapka feedback save ho gaya 🙏 {stars}
{('Feedback: ' + feedback_text) if feedback_text else ''}

Have another repair need? Just describe it! 🔧"""
    SESSION["customer"]["history"].append({"role": "assistant", "content": reply, "timestamp": _now()})

    worker_notify = f"⭐ Customer ne {rating}/5 rating di!\n{'Bahut badhiya kaam!' if rating >= 4 else 'Agle baar aur accha karenge! 💪'}"
    SESSION["worker"]["history"].append({"role": "assistant", "content": worker_notify, "timestamp": _now()})

    return jsonify({"customer_reply": reply, "worker_reply": worker_notify})

def _handle_customer_confirmation(message: str):
    message_lower = message.lower()
    if 'haan' in message_lower or 'yes' in message_lower or 'y' in message_lower:
        SESSION["pending_customer_confirmation"] = False
        SESSION["awaiting_rating"] = True
        
        reply = "Great! Worker ko 1 se 5 mein rate karo (5 = best).\nBas number bhejo, chaaho to ek line feedback bhi likh do."
        SESSION["customer"]["history"].append({"role": "assistant", "content": reply, "timestamp": _now()})
        return jsonify({"customer_reply": reply, "worker_reply": None})
    elif 'nahi' in message_lower or 'no' in message_lower or 'n' in message_lower:
        SESSION["pending_customer_confirmation"] = False
        
        reply = "We're sorry to hear that. We will review the job and contact you shortly."
        SESSION["customer"]["history"].append({"role": "assistant", "content": reply, "timestamp": _now()})
        
        worker_reply = "Customer keh rahe hain ki kaam theek se nahi hua. Agent aapse connect karega."
        SESSION["worker"]["history"].append({"role": "assistant", "content": worker_reply, "timestamp": _now()})
        
        return jsonify({"customer_reply": reply, "worker_reply": worker_reply})
    else:
        reply = "Please reply with Haan or Nahi."
        SESSION["customer"]["history"].append({"role": "assistant", "content": reply, "timestamp": _now()})
        return jsonify({"customer_reply": reply, "worker_reply": None})


def _process_decline(worker_data: dict, reason_code: str):
    """
    Update worker profile based on decline reason.
    This is the self-learning system — after many declines,
    matching gets smarter without the worker filling any forms.
    """
    job = SESSION.get("current_job", {})
    job_type = job.get("problem_type", "plumbing")

    if reason_code == "1":
        # Busy — mark unavailable for 3 hours
        worker_data['currently_available'] = False
        worker_data['available_after'] = (_now_dt() + timedelta(hours=3)).isoformat()

    elif reason_code == "2":
        # Too far — shrink radius
        current_radius = worker_data.get('preferred_radius_km', 5.0)
        worker_data['preferred_radius_km'] = max(current_radius - 0.5, 1.0)

    elif reason_code == "3":
        # Wrong skill — reduce specialization weight
        weights = worker_data.get('specialization_weights', {})
        if job_type in weights:
            weights[job_type] = max(weights[job_type] - 0.3, 0.0)
        worker_data['specialization_weights'] = weights

    elif reason_code == "4":
        # Low pay — raise minimum job value
        min_values = worker_data.get('minimum_job_value', {})
        price = SESSION.get("price_estimate", {})
        current_min = min_values.get(job_type, 0)
        job_value = price.get('fair_single_quote', 0)
        min_values[job_type] = max(current_min, job_value + 100)
        worker_data['minimum_job_value'] = min_values

    # reason_code == "5" — personal, no system update

    # Track decline
    worker_data.setdefault('decline_reasons', []).append({
        "job_id": job.get("id", "unknown"),
        "reason": reason_code,
        "timestamp": _now()
    })
    worker_data['jobs_declined'] = worker_data.get('jobs_declined', 0) + 1

    # Save
    save_worker(worker_data)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------
def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _now_ts() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")

def _now_dt() -> datetime:
    return datetime.now()



# ---------------------------------------------------------------------------
# WhatsApp (Meta) — Per-phone-number session store
# This is SEPARATE from the demo-UI's global SESSION dict above, so the
# website demo and the real WhatsApp bot never interfere with each other.
# ---------------------------------------------------------------------------
WA_SESSIONS = {}          # phone_number -> session dict
SEEN_MESSAGE_IDS = set()  # for deduplication of Meta webhook retries


def _new_wa_session(role: str) -> dict:
    return {
        "role": role,                      # "customer" | "worker"
        "history": [],
        "language": "hinglish",
        "state": "idle",                   # idle | awaiting_worker_selection | job_assigned | awaiting_completion | awaiting_rating
        "problem_analysis": None,
        "price_estimate": None,
        "matched_workers": [],
        "selected_worker": None,
        "current_job_id": None,
        "customer_phone": None,            # set on worker session once job is assigned
        "worker_phone": None,              # set on customer session once worker accepts
    }


def _get_wa_session(phone: str, role: str) -> dict:
    if phone not in WA_SESSIONS:
        WA_SESSIONS[phone] = _new_wa_session(role)
    return WA_SESSIONS[phone]


def _is_duplicate(msg_id: str) -> bool:
    """Meta retries webhook delivery if our response is slow. Dedup by message id."""
    if not msg_id:
        return False
    if msg_id in SEEN_MESSAGE_IDS:
        return True
    SEEN_MESSAGE_IDS.add(msg_id)
    # Keep the set small
    if len(SEEN_MESSAGE_IDS) > 2000:
        SEEN_MESSAGE_IDS.clear()
    return False


# ---------------------------------------------------------------------------
# Webhook helpers (Meta WhatsApp integration) — real state machine
# ---------------------------------------------------------------------------
def _webhook_customer_text(phone: str, body: str) -> str:
    sess = _get_wa_session(phone, "customer")
    sess["history"].append({"role": "user", "content": body})

    # ---- waiting for worker selection (1/2/3) ----
    if sess["state"] == "awaiting_worker_selection":
        stripped = body.strip()
        if stripped in ("1", "2", "3"):
            idx = int(stripped) - 1
            workers = sess.get("matched_workers", [])
            if idx >= len(workers):
                return "Sahi number bhejo — 1, 2, ya 3 🙏"

            chosen = workers[idx]
            worker_info = chosen["worker"]
            sess["selected_worker"] = worker_info
            sess["worker_phone"] = worker_info.get("phone", "").replace("+", "")
            sess["state"] = "job_assigned"

            # Ping the worker
            worker_phone = sess["worker_phone"]
            if worker_phone:
                w_sess = _get_wa_session(worker_phone, "worker")
                w_sess["state"] = "awaiting_response"
                w_sess["customer_phone"] = phone
                w_sess["current_job_id"] = sess.get("current_job_id")

                ping_text = generate_response("job_request", {
                    "job_description_hindi": sess.get("problem_analysis", {}).get("hindi_summary", body),
                    "distance": chosen.get("distance_km", "N/A"),
                    "expected_pay": sess.get("price_estimate", {}).get("fair_single_quote", "TBD"),
                }, "hinglish", "worker")
                _send_meta_message(worker_phone, ping_text)

            return (f"✅ *{worker_info['name']}* ko job bhej diya hai!\n"
                    f"Unka response aate hi aapko batayenge. 🔔")
        else:
            return "Please 1, 2, ya 3 reply karo worker choose karne ke liye 🙏"

    # ---- normal intent detection ----
    intent_result = detect_intent(body, sess["history"])
    intent = intent_result.get("intent", "general_question")
    sess["language"] = intent_result.get("language", "hinglish")

    if intent == "job_request":
        job_type = intent_result.get("extracted", {}).get("job_type", "general")
        analysis = {
            "problem_type": job_type, "specific_issue": body, "hindi_summary": body,
            "severity": "moderate", "urgency": intent_result.get("extracted", {}).get("urgency", "normal"),
            "diy_possible": False, "estimated_time_hours": 2,
            "materials_likely_needed": [], "confidence": 0.6,
        }
        price = estimate_price(analysis)
        workers = find_best_workers(DEFAULT_CUSTOMER_LAT, DEFAULT_CUSTOMER_LON, job_type)

        sess["problem_analysis"] = analysis
        sess["price_estimate"] = price
        sess["matched_workers"] = workers
        sess["state"] = "awaiting_worker_selection" if workers else "idle"
        sess["current_job_id"] = f"job_{phone}_{int(datetime.now().timestamp())}"

        if not workers:
            return "Maaf kijiye, abhi koi worker available nahi hai aapke area mein 🙏 Thodi der baad try karo."

        return generate_response("job_request", {
            "matched_workers": workers, "price_estimate": price, "problem_analysis": analysis
        }, sess["language"], "customer")

    if intent == "price_query":
        price = estimate_price_from_text(body)
        return generate_response("price_query", {"price_estimate": price}, sess["language"], "customer")

    return generate_response("greeting", {}, sess["language"], "customer")


def _webhook_customer_image(phone: str, img_bytes: bytes, caption: str = "") -> str:
    sess = _get_wa_session(phone, "customer")
    analysis = analyze_problem_image(img_bytes, caption)
    price = estimate_price(analysis)
    workers = find_best_workers(DEFAULT_CUSTOMER_LAT, DEFAULT_CUSTOMER_LON, analysis.get("problem_type", "general"))

    sess["problem_analysis"] = analysis
    sess["price_estimate"] = price
    sess["matched_workers"] = workers
    sess["state"] = "awaiting_worker_selection" if workers else "idle"
    sess["current_job_id"] = f"job_{phone}_{int(datetime.now().timestamp())}"

    if not workers:
        return "Maaf kijiye, abhi koi worker available nahi hai aapke area mein 🙏"

    return generate_response("job_request", {
        "matched_workers": workers, "price_estimate": price, "problem_analysis": analysis
    }, "hinglish", "customer")


def _webhook_worker_text(phone: str, body: str) -> str:
    sess = _get_wa_session(phone, "worker")
    sess["history"].append({"role": "user", "content": body})

    intent_result = detect_intent(body, sess["history"])
    intent = intent_result.get("intent", "general_question")

    # ---- worker accepting a pending job ----
    if sess["state"] == "awaiting_response" and intent == "job_accept":
        sess["state"] = "job_active"
        customer_phone = sess.get("customer_phone")

        if customer_phone:
            c_sess = _get_wa_session(customer_phone, "customer")
            c_sess["state"] = "job_active"
            worker = c_sess.get("selected_worker", {})
            confirm_text = generate_response("customer_worker_assigned", {
                "name":      worker.get("name", "Worker"),
                "shop_name": worker.get("shop_name", ""),
                "trust":     worker.get("trust_score", "N/A"),
                "jobs":      worker.get("jobs_completed", 0),
                "distance":  "nearby",
                "eta":       "10-15",
            }, c_sess["language"], "customer")
            _send_meta_message(customer_phone, confirm_text)

        return "✅ Bahut badhiya! Customer ko bata diya hai. Site par pahuncho 🚗\nKaam khatam hone par photo bhejo verification ke liye 📸"

    # ---- worker declining ----
    if sess["state"] == "awaiting_response" and intent == "job_decline":
        sess["state"] = "awaiting_decline_reason"
        return ("Theek hai! 🙏 Decline ka reason batao (number bhejo):\n"
                "1️⃣ Abhi busy hoon\n2️⃣ Bahut door hai\n3️⃣ Yeh skill nahi hai\n"
                "4️⃣ Rate kam hai\n5️⃣ Personal reason")

    if sess["state"] == "awaiting_decline_reason" and body.strip() in ("1", "2", "3", "4", "5"):
        sess["state"] = "idle"
        customer_phone = sess.get("customer_phone")
        if customer_phone:
            c_sess = _get_wa_session(customer_phone, "customer")
            c_sess["state"] = "awaiting_worker_selection"
            _send_meta_message(customer_phone,
                "⏳ Worker abhi available nahi hai. Doosra worker select karo — 1, 2, ya 3 phir se bhejo 🔄")
        return "Samajh gaya, dhanyawad! Agla kaam jald hi milega 🙏"

    return generate_response("greeting", {}, "hinglish", "worker")


def _webhook_worker_image(phone: str, img_bytes: bytes) -> str:
    sess = _get_wa_session(phone, "worker")
    job_desc = sess.get("current_job_id", "completion photo")

    verification = verify_completion(b"", img_bytes, str(job_desc))
    status = verification.get("verification_status", "verified")

    customer_phone = sess.get("customer_phone")
    if customer_phone:
        c_sess = _get_wa_session(customer_phone, "customer")
        c_sess["state"] = "awaiting_rating"
        _send_meta_message(customer_phone,
            "✅ *Kaam complete ho gaya!*\nWorker ne photo bheji hai. Kripya rating dijiye (1-5) ⭐")

    if status == "verified":
        sess["state"] = "idle"
        return "✅ Kaam verified! Customer ko rating dene ka message bheja gaya. ⭐"
    return "⚠️ Photo review mein hai. Customer se confirm karenge."



# Run
# ---------------------------------------------------------------------------
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    # ── Meta verification handshake (GET) ──────────────────────────────────
    if request.method == 'GET':
        mode      = request.args.get('hub.mode')
        token     = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        print(f"[webhook] GET received — mode={mode} token={token}")
        if mode == 'subscribe' and token == 'karigar2024':
            print("[webhook] ✅ Meta verification successful!")
            return challenge, 200
        print("[webhook] ❌ Token mismatch or wrong mode")
        return 'Forbidden', 403

    # ── Incoming WhatsApp message (POST) ───────────────────────────────────
    try:
        data    = request.json
        print(f"[webhook] POST received: {data}")

        entry   = data['entry'][0]
        changes = entry['changes'][0]
        value   = changes['value']

        if 'messages' not in value:
            return '', 200   # delivery receipt / status update — ignore

        msg         = value['messages'][0]
        from_number = msg['from']   # e.g. "919876543210"
        msg_type    = msg['type']   # text | image | audio
        msg_id      = msg.get('id', '')

        # Meta retries delivery if our response is slow — ignore repeats
        if _is_duplicate(msg_id):
            print(f"[webhook] Duplicate message {msg_id} — ignoring")
            return '', 200

        WORKER_PHONES = [p.strip().lstrip('+') for p in os.getenv("WORKER_PHONES", "").split(",") if p.strip()]
        is_worker = from_number in WORKER_PHONES

        reply_text = ""

        if msg_type == 'text':
            body = msg['text']['body'].strip()
            print(f"[webhook] Text from {from_number}: {body}")
            reply_text = _webhook_worker_text(from_number, body) if is_worker \
                         else _webhook_customer_text(from_number, body)

        elif msg_type == 'image':
            media_id  = msg['image']['id']
            caption   = msg['image'].get('caption', '')
            img_bytes = _download_meta_media(media_id)
            reply_text = _webhook_worker_image(from_number, img_bytes) if is_worker \
                         else _webhook_customer_image(from_number, img_bytes, caption)

        elif msg_type == 'audio':
            media_id    = msg['audio']['id']
            audio_bytes = _download_meta_media(media_id)
            from algorithms.voice import transcribe_voice
            transcript  = transcribe_voice(audio_bytes, 'audio/ogg')
            reply_text = _webhook_worker_text(from_number, transcript) if is_worker \
                         else _webhook_customer_text(from_number, transcript)

        if reply_text:
            _send_meta_message(from_number, reply_text)

    except Exception as e:
        print(f"[webhook] Error: {e}")
        import traceback; traceback.print_exc()

    return '', 200


def _download_meta_media(media_id: str) -> bytes:
    import requests
    token = os.getenv('META_TOKEN', '')
    url_res = requests.get(
        f'https://graph.facebook.com/v19.0/{media_id}',
        headers={'Authorization': f'Bearer {token}'}
    )
    media_url = url_res.json().get('url', '')
    if not media_url:
        return b''
    return requests.get(
        media_url,
        headers={'Authorization': f'Bearer {token}'}
    ).content


def _send_meta_message(to: str, body: str):
    import requests
    token    = os.getenv('META_TOKEN', '')
    phone_id = os.getenv('META_PHONE_ID', '')
    if not token or not phone_id:
        print("[webhook] ❌ META_TOKEN or META_PHONE_ID not set in .env")
        return
    for chunk in [body[i:i+4000] for i in range(0, len(body), 4000)]:
        r = requests.post(
            f'https://graph.facebook.com/v19.0/{phone_id}/messages',
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            },
            json={
                'messaging_product': 'whatsapp',
                'to': to,
                'type': 'text',
                'text': {'body': chunk}
            }
        )
        print(f"[webhook] Sent message → {r.status_code} {r.text[:100]}")

if __name__ == '__main__':
    print("\n" + "="*60)
    print("  🔧 KARIGAR AI — WhatsApp Demo Server")
    print("  Open http://localhost:5000 in your browser")
    print("="*60 + "\n")
    port = int(os.getenv("PORT", 5000))
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug_mode, host="0.0.0.0", port=port)