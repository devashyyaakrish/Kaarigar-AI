"""
Worker Matching — Haversine distance + weighted scoring.
Reads/writes from data/workers.json (flat file, no DB needed for demo).
"""

import json
import math
import os

# Default customer location: Jaipur city centre
DEFAULT_CUSTOMER_LAT = 26.9124
DEFAULT_CUSTOMER_LON = 75.7873

_DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "workers.json")


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------
def _load_all_workers() -> list:
    try:
        with open(_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[matching] Could not load workers: {e}")
        return []


def _save_all_workers(workers: list):
    try:
        with open(_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(workers, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[matching] Could not save workers: {e}")


def load_worker(worker_id: str) -> dict | None:
    for w in _load_all_workers():
        if w["id"] == worker_id:
            return w
    return None


def save_worker(worker_data: dict):
    workers = _load_all_workers()
    for i, w in enumerate(workers):
        if w["id"] == worker_data["id"]:
            workers[i] = worker_data
            _save_all_workers(workers)
            return
    # New worker — append
    workers.append(worker_data)
    _save_all_workers(workers)


# ---------------------------------------------------------------------------
# Haversine distance (km)
# ---------------------------------------------------------------------------
def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def _score_worker(worker: dict, distance_km: float, job_type: str) -> float:
    """
    Composite score (higher = better match).
    Components:
      - Trust score (0-10) × 3.0
      - Proximity bonus: 10 − distance_km (capped 0-10) × 2.5
      - Skill match: 1.0 if primary skill, 0.5 if secondary × 2.0
      - Jobs completed (log scale) × 1.0
    """
    trust = worker.get("trust_score", 5.0)
    proximity = max(0, 10 - distance_km)
    
    skill_weight = worker.get("specialization_weights", {}).get(job_type, 0)
    if skill_weight == 0:
        # Check if job_type is in skills list
        if job_type in worker.get("skills", []):
            skill_weight = 0.7
        elif "general" in worker.get("skills", []):
            skill_weight = 0.3

    completed = worker.get("jobs_completed", 0)
    experience = math.log10(completed + 1)

    score = (trust * 3.0) + (proximity * 2.5) + (skill_weight * 10 * 2.0) + (experience * 1.0)
    return round(score, 3)


# ---------------------------------------------------------------------------
# Main matching function
# ---------------------------------------------------------------------------
def find_best_workers(
    customer_lat: float,
    customer_lon: float,
    job_type: str,
    exclude_ids: list = None,
    top_n: int = 3,
) -> list:
    """
    Find top N workers for a given job type and customer location.
    Returns list of dicts: {worker, distance_km, eta_minutes, score}
    """
    if exclude_ids is None:
        exclude_ids = []

    all_workers = _load_all_workers()
    candidates = []

    for w in all_workers:
        if w["id"] in exclude_ids:
            continue
        if not w.get("currently_available", True):
            continue

        # Must have the required skill (or be general)
        worker_skills = w.get("skills", [])
        if job_type not in worker_skills and "general" not in worker_skills:
            continue

        # Distance check
        dist = _haversine(customer_lat, customer_lon, w["lat"], w["lon"])
        if dist > w.get("preferred_radius_km", 10.0):
            continue

        # Minimum job value check (skip if price not set yet)
        score = _score_worker(w, dist, job_type)
        eta = int(dist * 5 + 5)  # rough: 5 min/km + 5 min prep

        candidates.append({
            "worker":      w,
            "distance_km": round(dist, 1),
            "eta_minutes": eta,
            "score":       score,
        })

    # Sort by score descending
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:top_n]


# ---------------------------------------------------------------------------
# Post-job updates
# ---------------------------------------------------------------------------
def update_worker_after_review(worker_id: str, rating: int, job: dict):
    """Update trust score and job count after a completed job."""
    worker = load_worker(worker_id)
    if not worker:
        return

    # Bayesian-style trust update: blend old score with new rating
    old_trust = worker.get("trust_score", 5.0)
    completed = worker.get("jobs_completed", 0)
    # New trust = weighted average (more jobs = more stable)
    weight = min(completed, 50) / 50.0  # max weight at 50 jobs
    new_trust = old_trust * weight + (rating * 2) * (1 - weight)  # rating 1-5 → scale to 2-10
    new_trust = round(max(1.0, min(10.0, new_trust)), 2)

    worker["trust_score"] = new_trust
    worker["jobs_completed"] = completed + 1

    # Log the job
    worker.setdefault("job_history", []).append({
        "job_id":  job.get("id", "unknown"),
        "rating":  rating,
        "review":  job.get("review_text", ""),
        "type":    job.get("problem_type", "general"),
    })

    save_worker(worker)
    print(f"[matching] Worker {worker_id} trust updated: {old_trust} → {new_trust}")