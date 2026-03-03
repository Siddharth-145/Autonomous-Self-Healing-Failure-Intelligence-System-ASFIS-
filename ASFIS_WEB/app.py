from flask import Flask, render_template, request, redirect
import random
from datetime import datetime
import requests

app = Flask(__name__)

class FailureLogger:

    def __init__(self):
        self.logs = []

    def log_failure(self, component, severity, error, source="Manual", status="Open"):
        log = {
            "component": component,
            "severity": severity,
            "error": error,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": status,
            "source": source
        }
        self.logs.append(log)

    def generate_simulated_failure(self):
        components = ["Database", "API", "Auth", "Payment", "Server"]
        errors = ["Timeout", "Memory Leak", "Service Down", "High Latency"]

        self.log_failure(
            random.choice(components),
            random.randint(1, 5),
            random.choice(errors),
            source="Simulation"
        )

    def monitor_website(self, url):
        try:
            response = requests.get(url, timeout=5)

            if response.status_code >= 400:
                self.log_failure(
                    "Website",
                    5,
                    f"Error {response.status_code}",
                    source="Monitor"
                )
            else:
                # Log healthy response also for demo clarity
                self.log_failure(
                    "Website",
                    1,
                    "Website is healthy",
                    source="Monitor",
                    status="Closed"
                )

        except requests.exceptions.Timeout:
            self.log_failure(
                "Website",
                5,
                "Timeout error",
                source="Monitor"
            )

        except requests.exceptions.ConnectionError:
            self.log_failure(
                "Website",
                5,
                "Website unreachable",
                source="Monitor"
            )


logger = FailureLogger()


@app.route("/")
def home():
    return render_template("index.html", logs=logger.logs)


@app.route("/log", methods=["POST"])
def log():
    component = request.form["component"]
    severity = int(request.form["severity"])
    error = request.form["error"]

    logger.log_failure(component, severity, error)
    return redirect("/")


@app.route("/simulate")
def simulate():
    logger.generate_simulated_failure()
    return redirect("/")


@app.route("/monitor", methods=["POST"])
def monitor():
    url = request.form["url"]
    logger.monitor_website(url)
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)