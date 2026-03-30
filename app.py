import os
import logging
from functools import wraps
from flask import Flask, request, jsonify, render_template, redirect, url_for
from failure_logger import FailureLogger

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me-in-production")
app.config["DEBUG"]      = os.getenv("FLASK_DEBUG", "false").lower() == "true"
app.config["API_KEY"]    = os.getenv("ASFIS_API_KEY", "")

failure_logger = FailureLogger()


# ── Auth guard ────────────────────────────────────────────────────────────────

def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        expected = app.config.get("API_KEY", "")
        if expected and request.headers.get("X-API-Key", "") != expected:
            return jsonify({"error": "Unauthorized — invalid API key."}), 401
        return f(*args, **kwargs)
    return decorated


# ── UI routes ─────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    return render_template("index.html", logs=failure_logger.get_logs())


@app.route("/log", methods=["POST"])
def log_ui():
    component = request.form.get("component", "").strip()
    error     = request.form.get("error", "").strip()
    try:
        severity = int(request.form.get("severity", 1))
    except ValueError:
        severity = 1
    failure_logger.log_failure(component, severity, error)
    return redirect(url_for("home"))


@app.route("/simulate")
def simulate_ui():
    failure_logger.generate_simulated_failure()
    return redirect(url_for("home"))


@app.route("/monitor", methods=["POST"])
def monitor_ui():
    url    = request.form.get("url", "").strip()
    result = failure_logger.monitor_website(url)
    return render_template("index.html", logs=failure_logger.get_logs(), monitor=result)


@app.route("/propagate", methods=["POST"])
def propagate_ui():
    component = request.form.get("component", "").strip()
    result    = failure_logger.propagate_failure(component)
    return render_template("index.html", logs=failure_logger.get_logs(), result=result)


@app.route("/patterns", methods=["POST"])
def patterns_ui():
    result = failure_logger.analyze_patterns()
    return render_template("index.html", logs=failure_logger.get_logs(), patterns=result)


@app.route("/fix", methods=["POST"])
def fix_ui():
    component = request.form.get("component", "").strip()
    result    = failure_logger.simulate_fix(component)
    return render_template("index.html", logs=failure_logger.get_logs(), fix=result)


@app.route("/reliability", methods=["POST"])
def reliability_ui():
    result = failure_logger.reliability_score()
    return render_template("index.html", logs=failure_logger.get_logs(), reliability=result)


@app.route("/resolve/<int:log_id>", methods=["POST"])
def resolve_ui(log_id):
    strategy = request.form.get("strategy", "")
    note     = request.form.get("note", "Resolved via dashboard.")
    failure_logger.resolve_failure(log_id, strategy=strategy, note=note)
    return redirect(url_for("home"))


@app.route("/status/<int:log_id>", methods=["POST"])
def update_status_ui(log_id):
    failure_logger.update_status(log_id, request.form.get("status", "Open"))
    return redirect(url_for("home"))


# ── API routes ────────────────────────────────────────────────────────────────

@app.route("/api/log_failure", methods=["POST"])
@require_api_key
def api_log_failure():
    data   = request.get_json(silent=True) or {}
    result = failure_logger.log_failure(data.get("component",""), data.get("severity",1), data.get("error",""))
    return jsonify(result), 400 if "error" in result else 201


@app.route("/api/get_logs", methods=["GET"])
@require_api_key
def api_get_logs():
    return jsonify(failure_logger.get_logs())


@app.route("/api/simulate", methods=["POST"])
@require_api_key
def api_simulate():
    return jsonify(failure_logger.generate_simulated_failure()), 201


@app.route("/api/monitor", methods=["POST"])
@require_api_key
def api_monitor():
    data = request.get_json(silent=True) or {}
    url  = data.get("url", "")
    if not url:
        return jsonify({"error": "URL is required."}), 400
    return jsonify(failure_logger.monitor_website(url))


@app.route("/api/propagate", methods=["POST"])
@require_api_key
def api_propagate():
    data      = request.get_json(silent=True) or {}
    component = data.get("component", "")
    if not component:
        return jsonify({"error": "Component is required."}), 400
    return jsonify(failure_logger.propagate_failure(component))


@app.route("/api/patterns", methods=["GET"])
@require_api_key
def api_patterns():
    return jsonify(failure_logger.analyze_patterns())


@app.route("/api/fix", methods=["POST"])
@require_api_key
def api_fix():
    data      = request.get_json(silent=True) or {}
    component = data.get("component", "")
    if not component:
        return jsonify({"error": "Component is required."}), 400
    return jsonify(failure_logger.simulate_fix(component))


@app.route("/api/reliability", methods=["GET"])
@require_api_key
def api_reliability():
    return jsonify(failure_logger.reliability_score())


@app.route("/api/resolve/<int:log_id>", methods=["POST"])
@require_api_key
def api_resolve(log_id):
    data = request.get_json(silent=True) or {}
    return jsonify(failure_logger.resolve_failure(log_id, data.get("strategy",""), data.get("note","Resolved via API.")))


@app.route("/api/status/<int:log_id>", methods=["PATCH"])
@require_api_key
def api_update_status(log_id):
    data   = request.get_json(silent=True) or {}
    status = data.get("status", "")
    if not status:
        return jsonify({"error": "Status is required."}), 400
    return jsonify(failure_logger.update_status(log_id, status, data.get("note","")))


# ── AI fix endpoint (called by frontend fetch) ────────────────────────────────

@app.route("/api/ai_fix", methods=["POST"])
@require_api_key
def api_ai_fix():
    """
    Accepts: { component, error, severity }
    Returns: AI-generated healing recommendation JSON.
    If AI fails, falls back to rule-based simulate_fix automatically.
    """
    data      = request.get_json(silent=True) or {}
    component = data.get("component", "").strip()
    error     = data.get("error", "").strip()
    try:
        severity = int(data.get("severity", 1))
    except (TypeError, ValueError):
        severity = 1

    if not component or not error:
        return jsonify({"error": "component and error are required."}), 400

    result = failure_logger.ai_suggest_fix(component, error, severity)

    # If AI failed, fall back to rule-based
    if result.get("fallback") or "error" in result:
        log.warning("AI fix failed, falling back to rule-based for component=%s", component)
        fallback = failure_logger.simulate_fix(component)
        fallback["ai_powered"] = False
        fallback["fallback_reason"] = result.get("error", "AI unavailable")
        return jsonify(fallback)

    return jsonify(result)


# ── Error handlers ────────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found."}), 404

@app.errorhandler(500)
def server_error(e):
    log.error("Internal server error: %s", e)
    return jsonify({"error": "Internal server error."}), 500


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    log.info("Starting ASFIS on port %d (debug=%s)", port, app.config["DEBUG"])
    app.run(host="0.0.0.0", port=port, debug=app.config["DEBUG"])