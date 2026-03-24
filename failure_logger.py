import random
import json
from datetime import datetime
import requests


class FailureLogger:

    def __init__(self, file="failures.json"):
        self.file = file
        self.logs = self.load_logs()

        # Dependency Map
        self.dependencies = {
            "Database": [("API", 0.9)],
            "API": [("Frontend", 0.8)],
            "Auth": [("API", 0.7)],
            "Payment": [("API", 0.6)],
            "Server": [("API", 0.85)]
        }

    def load_logs(self):
        try:
            with open(self.file, "r") as f:
                return json.load(f)
        except:
            return []

    def save_logs(self):
        with open(self.file, "w") as f:
            json.dump(self.logs, f, indent=4)

    def generate_id(self):
        return max([log["id"] for log in self.logs], default=0) + 1

    def validate(self, component, severity, error):
        if not component or not error:
            return False, "Component and error required"

        if not (1 <= severity <= 5):
            return False, "Severity must be between 1-5"

        return True, "Valid"

    def log_failure(self, component, severity, error, source="Manual"):
        valid, msg = self.validate(component, severity, error)

        if not valid:
            return {"error": msg}

        log = {
            "id": self.generate_id(),
            "component": component,
            "severity": severity,
            "error": error,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "Open",
            "source": source
        }

        self.logs.append(log)
        self.save_logs()

        return {"message": "Failure logged successfully", "log": log}

    def generate_simulated_failure(self):
        components = list(self.dependencies.keys())
        errors = [
            "Connection timeout",
            "Memory leak detected",
            "Service unavailable",
            "High latency",
            "Authentication failed"
        ]

        return self.log_failure(
            random.choice(components),
            random.randint(1, 5),
            random.choice(errors),
            source="Simulation"
        )

    def monitor_website(self, url):
        try:
            response = requests.get(url, timeout=5)

            if response.status_code >= 500:
                return self.log_failure("Website", 5, f"Server error {response.status_code}", "Monitor")

            elif response.status_code >= 400:
                return self.log_failure("Website", 3, f"Client error {response.status_code}", "Monitor")

            else:
                return {
                    "component": "Website",
                    "status": "Healthy",
                    "message": "Website is reachable and working fine"
                }

        except:
            return self.log_failure("Website", 5, "Website unreachable", "Monitor")

    def get_logs(self):
        return self.logs

    def update_status(self, log_id, status):
        for log in self.logs:
            if log["id"] == log_id:
                log["status"] = status
                self.save_logs()
                return {"message": "Updated successfully"}

        return {"error": "Log not found"}

    # 🔥 CORE MODULE
    def propagate_failure(self, component):

        visited = set()
        impact_scores = {component: 1.0}  # initial failure impact

        queue = [component]

        while queue:
            current = queue.pop(0)  
            visited.add(current)

            for dep, weight in self.dependencies.get(current, []):
                new_impact = impact_scores[current] * weight

                if dep not in impact_scores or new_impact > impact_scores[dep]:
                    impact_scores[dep] = new_impact

                if dep not in visited:
                    queue.append(dep)

        return {
            "source": component,
            "impact_propagation": impact_scores,
            "critical_components": [
                comp for comp, score in impact_scores.items() if score > 0.7
            ]
        }
        
    def analyze_patterns(self):
        if not self.logs:
            return {"message": "No data available"}

        component_count = {}
        error_count = {}
        high_severity = 0

        for log in self.logs:
            # Count components
            comp = log["component"]
            component_count[comp] = component_count.get(comp, 0) + 1

            # Count errors
            err = log["error"]
            error_count[err] = error_count.get(err, 0) + 1

            # High severity
            if log["severity"] >= 4:
                high_severity += 1

        most_failed_component = max(component_count, key=component_count.get)
        most_common_error = max(error_count, key=error_count.get)

        return {
            "most_failed_component": most_failed_component,
            "most_common_error": most_common_error,
            "high_severity_count": high_severity,
            "component_distribution": component_count
        }
        
    def simulate_fix(self, component):

        # Get related failures
        related_logs = [log for log in self.logs if log["component"] == component]

        if not related_logs:
            return {"message": "No failure history"}

        avg_severity = sum(log["severity"] for log in related_logs) / len(related_logs)
        failure_count = len(related_logs)

        # Decision logic
        if avg_severity >= 4:
            fix = "Immediate system restart"
            base_prob = 0.85
        elif avg_severity >= 3:
            fix = "Service restart and monitoring"
            base_prob = 0.70
        else:
            fix = "Minor patch / configuration fix"
            base_prob = 0.55

        # Adjust probability based on frequency
        if failure_count > 5:
            base_prob -= 0.1  # repeated failures reduce confidence

        outcome = "Likely Recovery" if base_prob > 0.7 else "Uncertain Recovery"

        return {
            "component": component,
            "avg_severity": round(avg_severity, 2),
            "failure_count": failure_count,
            "suggested_fix": fix,
            "success_probability": round(base_prob, 2),
            "expected_outcome": outcome
        }
        
    def reliability_score(self):

        if not self.logs:
            return {"message": "No data available"}

        component_scores = {}

        for log in self.logs:
            comp = log["component"]
            severity = log["severity"]

            # Weight severity more strongly
            score = severity * 2

            component_scores[comp] = component_scores.get(comp, 0) + score

        reliability = {}

        for comp, score in component_scores.items():
            rel = max(0, 100 - score)
            reliability[comp] = rel

        # Find weakest component
        weakest = min(reliability, key=reliability.get)

        return {
            "reliability_scores": reliability,
            "weakest_component": weakest
        }