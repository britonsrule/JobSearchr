"""
Job Search Web App — Flask backend
Run with: python app.py
Then open: http://localhost:5000
"""

import csv
import json
import os
import queue
import threading
import webbrowser
from datetime import date, timedelta
from threading import Timer
from flask import Flask, render_template, request, redirect, url_for, jsonify, Response, stream_with_context

app = Flask(__name__)

# ── File paths ──────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
TRACKER_FILE  = os.path.join(BASE_DIR, "applications.csv")
JOBS_FILE     = os.path.join(BASE_DIR, "jobs_results.csv")
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

COLUMNS = [
    "date_applied", "employer_name", "job_title", "job_url",
    "resume_used", "source", "status", "notes",
]
VALID_STATUSES = ["Applied", "Phone Screen", "Interview", "Offer", "Rejected", "Withdrawn"]

DEFAULT_SETTINGS = {
    "location": "Seattle, WA",
    "hours_old": 24,
    "results_per_search": 100,
    "sites": ["indeed", "linkedin"],
    "exclude_companies": ["amazon", "aws"],
    "searches": [],
    "high_signal": [],
    "med_signal": [],
    "neg_signal": [],
}

# ── Settings helpers ─────────────────────────────────────
def load_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE) as f:
            return {**DEFAULT_SETTINGS, **json.load(f)}
    return DEFAULT_SETTINGS.copy()

def save_settings(data: dict):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ── CSV helpers ──────────────────────────────────────────
def init_tracker():
    if not os.path.exists(TRACKER_FILE):
        with open(TRACKER_FILE, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=COLUMNS).writeheader()

def load_apps():
    init_tracker()
    with open(TRACKER_FILE, newline="") as f:
        return list(csv.DictReader(f))

def save_apps(apps):
    with open(TRACKER_FILE, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(apps)

def load_jobs():
    if not os.path.exists(JOBS_FILE):
        return []
    with open(JOBS_FILE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

# ── Application routes ────────────────────────────────────

@app.route("/")
def index():
    apps = sorted(load_apps(), key=lambda x: x["date_applied"], reverse=True)
    counts = {s: 0 for s in VALID_STATUSES}
    for a in apps:
        if a.get("status") in counts:
            counts[a["status"]] += 1
    active = counts["Phone Screen"] + counts["Interview"] + counts["Offer"]
    today = date.today()
    days_since_sunday = (today.weekday() + 1) % 7
    week_start = today - timedelta(days=days_since_sunday)
    week_end   = week_start + timedelta(days=6)
    week_apps  = [a for a in apps
                  if week_start.isoformat() <= a["date_applied"] <= week_end.isoformat()]
    return render_template("index.html",
        apps=apps, counts=counts, active=active,
        week_apps=week_apps,
        week_start=week_start.strftime("%b %d"),
        week_end=week_end.strftime("%b %d, %Y"),
        statuses=VALID_STATUSES,
        today=date.today().isoformat(),
    )

@app.route("/add", methods=["POST"])
def add():
    entry = {col: request.form.get(col, "").strip() for col in COLUMNS}
    if not entry["date_applied"]:
        entry["date_applied"] = date.today().isoformat()
    apps = load_apps()
    apps.append(entry)
    save_apps(apps)
    return redirect(url_for("index"))

@app.route("/update/<int:idx>", methods=["POST"])
def update(idx):
    apps = sorted(load_apps(), key=lambda x: x["date_applied"], reverse=True)
    if 0 <= idx < len(apps):
        for col in COLUMNS:
            val = request.form.get(col)
            if val is not None:
                apps[idx][col] = val.strip()
    save_apps(sorted(apps, key=lambda x: x["date_applied"], reverse=True))
    return redirect(url_for("index"))

@app.route("/delete/<int:idx>", methods=["POST"])
def delete(idx):
    apps = sorted(load_apps(), key=lambda x: x["date_applied"], reverse=True)
    if 0 <= idx < len(apps):
        apps.pop(idx)
    save_apps(apps)
    return redirect(url_for("index"))

@app.route("/api/app/<int:idx>")
def get_app(idx):
    apps = sorted(load_apps(), key=lambda x: x["date_applied"], reverse=True)
    if 0 <= idx < len(apps):
        return jsonify(apps[idx])
    return jsonify({}), 404

# ── Jobs route ────────────────────────────────────────────

@app.route("/jobs")
def jobs():
    all_jobs = load_jobs()
    q         = request.args.get("q", "").lower()
    min_score = int(request.args.get("min_score", 0))
    if q:
        all_jobs = [j for j in all_jobs
                    if q in j.get("title","").lower() or q in j.get("company","").lower()]
    if min_score:
        all_jobs = [j for j in all_jobs
                    if int(j.get("relevance_score", 0) or 0) >= min_score]
    all_jobs.sort(key=lambda x: int(x.get("relevance_score", 0) or 0), reverse=True)
    return render_template("jobs.html", jobs=all_jobs, q=q, min_score=min_score)

# ── Settings routes ───────────────────────────────────────

@app.route("/settings", methods=["GET"])
def settings():
    cfg = load_settings()
    return render_template("settings.html", cfg=cfg)

@app.route("/settings/save", methods=["POST"])
def settings_save():
    cfg = load_settings()

    # Scalar fields
    cfg["location"]           = request.form.get("location", "Seattle, WA").strip()
    cfg["hours_old"]          = int(request.form.get("hours_old", 24))
    cfg["results_per_search"] = int(request.form.get("results_per_search", 100))

    # Sites checkboxes
    cfg["sites"] = request.form.getlist("sites")

    # List fields — one item per line, strip blanks
    def parse_lines(field):
        return [l.strip() for l in request.form.get(field, "").splitlines() if l.strip()]

    cfg["searches"]          = parse_lines("searches")
    cfg["exclude_companies"] = parse_lines("exclude_companies")
    cfg["high_signal"]       = parse_lines("high_signal")
    cfg["med_signal"]        = parse_lines("med_signal")
    cfg["neg_signal"]        = parse_lines("neg_signal")

    save_settings(cfg)
    return redirect(url_for("settings") + "?saved=1")

# ── Search runner (SSE streaming) ─────────────────────────

_search_queue = None
_search_running = False

@app.route("/search/run")
def search_run():
    """Stream search log output to the browser via Server-Sent Events."""
    global _search_queue, _search_running

    if _search_running:
        def already_running():
            yield "data: Search already in progress.\n\n"
        return Response(stream_with_context(already_running()), mimetype="text/event-stream")

    _search_queue   = queue.Queue()
    _search_running = True

    def run_search():
        global _search_running
        try:
            from job_search import run
            run(log=lambda msg: _search_queue.put(msg))
        except Exception as e:
            _search_queue.put(f"ERROR: {e}")
        finally:
            _search_queue.put(None)  # sentinel
            _search_running = False

    threading.Thread(target=run_search, daemon=True).start()

    def stream():
        while True:
            msg = _search_queue.get()
            if msg is None:
                yield "data: \n\ndata: __DONE__\n\n"
                break
            # Escape for SSE
            for line in msg.splitlines():
                yield f"data: {line}\n"
            yield "\n"

    return Response(stream_with_context(stream()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.route("/search/status")
def search_status():
    return jsonify({"running": _search_running})

# ── Boot ──────────────────────────────────────────────────

if __name__ == "__main__":
    Timer(1.0, lambda: webbrowser.open("http://localhost:5000")).start()
    print("\n  Job Search App running → http://localhost:5000")
    print("  Press Ctrl+C to stop.\n")
    app.run(debug=False, port=5000, threaded=True)
