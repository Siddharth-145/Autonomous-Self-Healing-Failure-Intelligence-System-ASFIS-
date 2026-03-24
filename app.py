from flask import Flask, request, jsonify, render_template, redirect
from failure_logger import FailureLogger

app = Flask(__name__)

logger = FailureLogger()

# ---------------- UI ----------------
@app.route("/")
def home():
    return render_template("index.html", logs=logger.get_logs())


# ---------------- API ----------------
@app.route("/api/log_failure", methods=["POST"])
def log_failure():
    data = request.json
    result = logger.log_failure(
        data.get("component"),
        data.get("severity"),
        data.get("error")
    )
    return jsonify(result)


@app.route("/api/get_logs", methods=["GET"])
def get_logs():
    return jsonify(logger.get_logs())


@app.route("/api/simulate", methods=["POST"])
def simulate():
    return jsonify(logger.generate_simulated_failure())


@app.route("/api/monitor", methods=["POST"])
def monitor():
    data = request.json
    return jsonify(logger.monitor_website(data.get("url")))


@app.route("/api/propagate", methods=["POST"])
def propagate():
    data = request.json
    return jsonify(logger.propagate_failure(data.get("component")))


# ---------------- UI FORMS ----------------
@app.route("/log", methods=["POST"])
def log_ui():
    logger.log_failure(
        request.form["component"],
        int(request.form["severity"]),
        request.form["error"]
    )
    return redirect("/")


@app.route("/simulate")
def simulate_ui():
    logger.generate_simulated_failure()
    return redirect("/")


@app.route("/monitor", methods=["POST"])
def monitor_ui():
    result = logger.monitor_website(request.form["url"])
    return render_template(
        "index.html",
        logs=logger.get_logs(),
        monitor=result
    )


@app.route("/propagate", methods=["POST"])
def propagate_ui():
    result = logger.propagate_failure(request.form["component"])
    return render_template("index.html", logs=logger.get_logs(), result=result)

@app.route("/api/patterns", methods=["GET"])
def patterns():
    return jsonify(logger.analyze_patterns())

@app.route("/patterns", methods=["POST"])
def patterns_ui():
    result = logger.analyze_patterns()
    return render_template("index.html", logs=logger.get_logs(), patterns=result)

@app.route("/api/fix", methods=["POST"])
def fix():
    data = request.json
    return jsonify(logger.simulate_fix(data.get("component")))

@app.route("/fix", methods=["POST"])
def fix_ui():
    result = logger.simulate_fix(request.form["component"])
    return render_template(
        "index.html",
        logs=logger.get_logs(),
        fix=result
    )
    
@app.route("/api/reliability", methods=["GET"])
def reliability():
    return jsonify(logger.reliability_score())

@app.route("/reliability", methods=["POST"])
def reliability_ui():
    result = logger.reliability_score()
    return render_template(
        "index.html",
        logs=logger.get_logs(),
        reliability=result
    )
    
if __name__ == "__main__":
    app.run(debug=True)