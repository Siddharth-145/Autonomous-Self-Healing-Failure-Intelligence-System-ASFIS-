import random
import sqlite3
import logging
import json
from datetime import datetime
from contextlib import contextmanager

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DB_FILE = "asfis.db"

HEALING_STRATEGIES = {
    "restart":  {"name": "Service Restart",          "description": "Stop and restart the failing service process.",                  "base_probability": 0.85, "best_for": "Transient errors, memory leaks, connection timeouts"},
    "failover": {"name": "Failover to Backup",        "description": "Redirect traffic to a standby/backup instance.",                "base_probability": 0.90, "best_for": "Full component outages where a backup exists"},
    "throttle": {"name": "Load Throttling",           "description": "Rate-limit incoming requests to reduce component pressure.",     "base_probability": 0.70, "best_for": "High latency, overload, performance degradation"},
    "rollback": {"name": "Version Rollback",          "description": "Revert the component to its last stable deployed version.",      "base_probability": 0.80, "best_for": "Failures after a recent deployment or config change"},
    "isolate":  {"name": "Circuit Breaker Isolation", "description": "Cut the component from the dependency chain to stop propagation.","base_probability": 0.75, "best_for": "Cascading failures affecting downstream components"},
    "escalate": {"name": "Human Escalation",          "description": "Alert on-call engineer. Auto-strategies have low confidence.",   "base_probability": 0.60, "best_for": "Unknown errors, severity 5, or repeated auto-fix failures"},
}

DEPENDENCY_MAP = {
    "Database": [("API", 0.9)],
    "API":      [("Frontend", 0.8)],
    "Auth":     [("API", 0.7)],
    "Payment":  [("API", 0.6)],
    "Server":   [("API", 0.85)],
    "Cache":    [("API", 0.75), ("Database", 0.5)],
    "Queue":    [("API", 0.65)],
    "Website":  [],
}

AI_SYSTEM_PROMPT = """You are ASFIS — an Autonomous Self-Healing Failure Intelligence engine.

You receive structured failure data and must respond ONLY with a valid JSON object. No markdown, no explanation, no extra text.

Analyze the failure based on:
- The exact error message wording
- The component type (Database, API, Auth, Payment, Server, Cache, Queue, Website, etc.)
- Severity level (1=low, 5=critical)
- Historical failure patterns
- Downstream dependency risk

Respond with exactly this JSON structure:
{
  "strategy": "<one of: restart | failover | throttle | rollback | isolate | escalate>",
  "strategy_name": "<human readable name>",
  "confidence": <float 0.0-1.0>,
  "root_cause": "<one sentence: most likely root cause based on the error>",
  "reasoning": "<2-3 sentences: why this strategy for this specific error and component>",
  "immediate_steps": ["<step 1>", "<step 2>", "<step 3>"],
  "preventive_measures": ["<measure 1>", "<measure 2>"],
  "estimated_recovery_time": "<e.g. 2-5 minutes | 10-30 minutes | 1-2 hours>",
  "risk_level": "<Low | Medium | High | Critical>",
  "escalate_if": "<condition under which a human must intervene>"
}

Be specific to the actual error text. A 'connection timeout' on a Database needs different steps than a 'memory leak' on an API."""


class FailureLogger:

    def __init__(self, db_file: str = DB_FILE):
        self.db_file = db_file
        self._init_db()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            logger.error("DB error: %s", e)
            raise
        finally:
            conn.close()

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS failures (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    component        TEXT    NOT NULL,
                    severity         INTEGER NOT NULL CHECK(severity BETWEEN 1 AND 5),
                    error            TEXT    NOT NULL,
                    status           TEXT    NOT NULL DEFAULT 'Open',
                    source           TEXT    NOT NULL DEFAULT 'Manual',
                    strategy_used    TEXT,
                    resolution_note  TEXT,
                    timestamp        TEXT    NOT NULL,
                    resolved_at      TEXT
                )
            """)
        logger.info("Database initialised: %s", self.db_file)

    def _validate(self, component, severity, error):
        if not component or not component.strip():
            return False, "Component name is required."
        if not error or not error.strip():
            return False, "Error description is required."
        if not isinstance(severity, int) or not (1 <= severity <= 5):
            return False, "Severity must be an integer between 1 and 5."
        return True, "Valid"

    def log_failure(self, component: str, severity, error: str, source: str = "Manual"):
        try:
            severity = int(severity)
        except (TypeError, ValueError):
            return {"error": "Severity must be a number between 1 and 5."}
        valid, msg = self._validate(component, severity, error)
        if not valid:
            return {"error": msg}
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    "INSERT INTO failures (component, severity, error, source, timestamp) VALUES (?, ?, ?, ?, ?)",
                    (component.strip(), severity, error.strip(), source, timestamp),
                )
                log_id = cur.lastrowid
            log = self._get_log_by_id(log_id)
            logger.info("Failure logged — id=%d component=%s severity=%d", log_id, component, severity)
            return {"message": "Failure logged successfully.", "log": log}
        except sqlite3.Error as e:
            return {"error": f"Database error: {e}"}

    def get_logs(self):
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM failures ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]

    def _get_log_by_id(self, log_id):
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM failures WHERE id = ?", (log_id,)).fetchone()
        return dict(row) if row else None

    def update_status(self, log_id: int, status: str, note: str = ""):
        allowed = {"Open", "In Progress", "Closed", "Escalated"}
        if status not in allowed:
            return {"error": f"Status must be one of: {', '.join(allowed)}"}
        resolved_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if status == "Closed" else None
        try:
            with self._conn() as conn:
                conn.execute(
                    "UPDATE failures SET status=?, resolution_note=?, resolved_at=? WHERE id=?",
                    (status, note, resolved_at, log_id),
                )
            return {"message": f"Status updated to '{status}'.", "resolved_at": resolved_at}
        except sqlite3.Error as e:
            return {"error": f"Database error: {e}"}

    def resolve_failure(self, log_id: int, strategy: str = "", note: str = ""):
        resolved_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with self._conn() as conn:
                conn.execute(
                    "UPDATE failures SET status='Closed', strategy_used=?, resolution_note=?, resolved_at=? WHERE id=?",
                    (strategy, note, resolved_at, log_id),
                )
            return {"message": "Failure marked as Closed.", "log_id": log_id, "resolved_at": resolved_at, "strategy_used": strategy}
        except sqlite3.Error as e:
            return {"error": f"Database error: {e}"}

    def generate_simulated_failure(self):
        components = list(DEPENDENCY_MAP.keys())
        errors = [
            "Connection timeout", "Memory leak detected", "Service unavailable",
            "High latency spike", "Authentication failed", "Disk I/O overload",
            "Null pointer exception", "Rate limit exceeded",
            "SSL certificate expired", "Database deadlock detected",
        ]
        return self.log_failure(random.choice(components), random.randint(1, 5), random.choice(errors), source="Simulation")

    def monitor_website(self, url: str):
        if not REQUESTS_AVAILABLE:
            return {"error": "requests library not installed."}
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code >= 500:
                return self.log_failure("Website", 5, f"Server error {resp.status_code}", "Monitor")
            elif resp.status_code >= 400:
                return self.log_failure("Website", 3, f"Client error {resp.status_code}", "Monitor")
            return {"component": "Website", "status": "Healthy", "message": f"Website is reachable. Status: {resp.status_code}", "response_time_ms": round(resp.elapsed.total_seconds() * 1000, 2)}
        except requests.exceptions.Timeout:
            return self.log_failure("Website", 4, "Request timed out after 5s", "Monitor")
        except requests.exceptions.ConnectionError:
            return self.log_failure("Website", 5, "Website unreachable — connection refused", "Monitor")
        except requests.exceptions.RequestException as e:
            return self.log_failure("Website", 3, f"Monitor error: {str(e)}", "Monitor")

    def propagate_failure(self, component: str):
        impact_scores = {component: 1.0}
        visited = set()
        queue = [component]
        while queue:
            current = queue.pop(0)
            visited.add(current)
            for dep, weight in DEPENDENCY_MAP.get(current, []):
                new_impact = impact_scores[current] * weight
                if dep not in impact_scores or new_impact > impact_scores[dep]:
                    impact_scores[dep] = round(new_impact, 3)
                if dep not in visited:
                    queue.append(dep)
        critical = [c for c, s in impact_scores.items() if s > 0.7 and c != component]
        return {
            "source": component, "impact_propagation": impact_scores,
            "critical_components": critical, "affected_components": list(impact_scores.keys()),
            "impact_level": "Critical" if max(impact_scores.values()) > 0.8 else "Moderate",
        }

    def analyze_patterns(self):
        logs = self.get_logs()
        if not logs:
            return {"message": "No data available yet."}
        component_count, error_count, high_severity, open_count, closed_count = {}, {}, 0, 0, 0
        for log in logs:
            component_count[log["component"]] = component_count.get(log["component"], 0) + 1
            error_count[log["error"]] = error_count.get(log["error"], 0) + 1
            if log["severity"] >= 4: high_severity += 1
            if log["status"] == "Closed": closed_count += 1
            else: open_count += 1
        return {
            "most_failed_component": max(component_count, key=component_count.get),
            "most_common_error": max(error_count, key=error_count.get),
            "high_severity_count": high_severity,
            "component_distribution": component_count,
            "total_failures": len(logs), "open_failures": open_count, "closed_failures": closed_count,
            "resolution_rate_pct": round((closed_count / len(logs)) * 100, 1),
        }

    def simulate_fix(self, component: str):
        logs = self.get_logs()
        related = [l for l in logs if l["component"] == component]
        if not related:
            return {"message": f"No failure history found for '{component}'."}
        avg_severity = sum(l["severity"] for l in related) / len(related)
        failure_count = len(related)
        open_failures = [l for l in related if l["status"] != "Closed"]
        recent_errors = [l["error"] for l in related[-5:]]
        has_propagation_risk = component in DEPENDENCY_MAP
        scores = {
            "restart":  max(0.35, 0.85 - (0.10 if avg_severity >= 4 else 0) - (0.10 if failure_count > 5 else 0)),
            "failover": 0.90 if avg_severity >= 4 else 0.55,
            "throttle": 0.75 if any(k in e.lower() for e in recent_errors for k in ["latency","overload","slow","timeout","rate"]) else 0.45,
            "rollback": 0.70 if failure_count <= 3 else 0.50,
            "isolate":  0.80 if has_propagation_risk else 0.40,
            "escalate": 0.90 if (avg_severity >= 4.5 or len(open_failures) > 3) else 0.35,
        }
        best_key = max(scores, key=scores.get)
        best_prob = round(scores[best_key], 2)
        all_strategies = sorted([
            {"key": k, "name": v["name"], "description": v["description"], "confidence": round(scores[k], 2), "best_for": v["best_for"]}
            for k, v in HEALING_STRATEGIES.items()
        ], key=lambda x: x["confidence"], reverse=True)
        return {
            "component": component, "avg_severity": round(avg_severity, 2),
            "failure_count": failure_count, "open_failures": len(open_failures),
            "recommended_strategy": HEALING_STRATEGIES[best_key]["name"],
            "strategy_key": best_key,
            "strategy_description": HEALING_STRATEGIES[best_key]["description"],
            "success_probability": best_prob,
            "expected_outcome": "High confidence recovery" if best_prob >= 0.80 else "Likely recovery" if best_prob >= 0.65 else "Uncertain — manual review recommended",
            "all_strategies": all_strategies,
        }

    # ── AI-powered fix (Claude API) ────────────────────────────────

    def ai_suggest_fix(self, component: str, error: str, severity: int):
        """
        Calls Claude API with full failure context to get a smart,
        error-specific healing recommendation.
        Falls back to rule-based simulate_fix if AI is unavailable.
        """
        if not REQUESTS_AVAILABLE:
            return {"error": "requests library not installed.", "fallback": True}

        all_logs = self.get_logs()
        related = [l for l in all_logs if l["component"] == component]
        history = [{"error": l["error"], "severity": l["severity"], "status": l["status"], "timestamp": l["timestamp"]} for l in related[-5:]]
        downstream = [dep for dep, _ in DEPENDENCY_MAP.get(component, [])]

        user_prompt = f"""Analyze this system failure and recommend the best healing strategy:

Component: {component}
Error: {error}
Severity: {severity}/5
Downstream components at risk: {downstream if downstream else 'None'}
Total prior failures for this component: {len(related)}
Recent failure history:
{json.dumps(history, indent=2) if history else 'No prior history'}

Respond only with the JSON object."""

        try:
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"Content-Type": "application/json"},
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 1000,
                    "system": AI_SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": user_prompt}],
                },
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()

            raw = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()
            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
                raw = raw.strip()

            result = json.loads(raw)
            result.update({"component": component, "error": error, "severity": severity, "ai_powered": True})
            logger.info("AI fix generated — component=%s strategy=%s", component, result.get("strategy"))
            return result

        except requests.exceptions.Timeout:
            logger.warning("AI fix timed out for component=%s", component)
            return {"error": "AI request timed out.", "fallback": True}
        except requests.exceptions.RequestException as e:
            logger.error("AI request failed: %s", e)
            return {"error": f"AI request failed: {e}", "fallback": True}
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("AI parse error: %s", e)
            return {"error": "Could not parse AI response.", "fallback": True}

    # ── Smart fix (keyword + component + history aware) ────────────

    def smart_fix(self, component: str, error: str, severity: int):
        """
        Intelligent rule-based fix that combines:
        - Error keyword analysis
        - Component type awareness
        - Historical failure data
        Returns only: strategy, strategy_name, confidence, root_cause, reasoning
        """
        error_lower  = error.lower()
        comp_lower   = component.lower()
        all_logs     = self.get_logs()
        related      = [l for l in all_logs if l["component"] == component]
        failure_count = len(related)
        open_failures = sum(1 for l in related if l["status"] != "Closed")
        has_downstream = bool(DEPENDENCY_MAP.get(component))

        # ── Keyword → strategy + root cause mapping ──
        rules = [
            (["timeout", "timed out", "connection refused", "unreachable"],
             "restart", "Network or connection layer is not responding.",
             "Connection-level failures are typically transient. A service restart clears stale connections and resets the connection pool."),

            (["memory leak", "out of memory", "oom", "heap"],
             "restart", "Process memory has grown unchecked, exhausting available RAM.",
             "Memory leaks require a process restart to reclaim memory. Long-term fix needs profiling to find the leaking code path."),

            (["latency", "slow", "high response", "overload", "queue full", "backpressure"],
             "throttle", "Incoming request volume is exceeding the component's processing capacity.",
             "Load throttling reduces pressure immediately. Pair with autoscaling to address the root capacity gap."),

            (["rate limit", "429", "too many requests"],
             "throttle", "Request rate is exceeding the allowed threshold set by the service.",
             "Apply rate limiting on the client side and introduce exponential backoff to respect the upstream quota."),

            (["disk", "i/o", "storage", "no space", "write failed"],
             "escalate", "Disk or storage layer is full or failing, requiring manual intervention.",
             "Disk issues cannot be auto-resolved safely. An engineer must free space, expand storage, or replace the failing disk."),

            (["auth", "unauthorized", "403", "401", "permission denied", "credentials"],
             "rollback", "Authentication or authorization configuration has broken, likely after a recent change.",
             "Auth failures after deployment suggest a config regression. Rolling back restores the last known working credentials or policy."),

            (["ssl", "certificate", "tls", "expired"],
             "escalate", "SSL/TLS certificate has expired or is misconfigured.",
             "Certificate renewal requires manual action. Automated renewal (e.g. Let's Encrypt) should be configured to prevent recurrence."),

            (["deadlock", "lock wait", "transaction", "rollback"],
             "restart", "Database is stuck in a deadlock state between concurrent transactions.",
             "Restarting the database service clears active locks. Long-term fix requires query optimization to reduce lock contention."),

            (["null pointer", "null reference", "segfault", "exception", "crash"],
             "rollback", "Application-level crash caused by a code defect, likely introduced in a recent deployment.",
             "Code-level exceptions after deployment point to a regression. Rolling back to the previous version restores stability while the bug is fixed."),

            (["unavailable", "down", "offline", "not responding"],
             "failover" if has_downstream else "restart",
             "The component is completely unresponsive.",
             "Full unavailability with downstream dependencies warrants failover to a backup instance to maintain service continuity." if has_downstream else "Service is down with no downstream risk. Restarting is the fastest recovery path."),

            (["server error", "500", "502", "503", "504"],
             "restart", "The server is returning error codes, indicating internal processing failure.",
             "5xx errors from a server typically indicate a crashed process or misconfigured upstream. Restarting clears the bad state."),
        ]

        strategy_key = None
        root_cause   = None
        reasoning    = None

        for keywords, strat, cause, reason in rules:
            if any(kw in error_lower for kw in keywords):
                strategy_key = strat
                root_cause   = cause
                reasoning    = reason
                break

        # ── Component-type override ──
        if not strategy_key:
            if "database" in comp_lower or "db" in comp_lower:
                strategy_key = "restart"
                root_cause   = "Database process encountered an unrecognised error state."
                reasoning    = "Database restarts are generally safe and fast, clearing bad connection states and in-memory corruption."
            elif "payment" in comp_lower:
                strategy_key = "escalate"
                root_cause   = "Payment component failure requires human review to avoid financial data risk."
                reasoning    = "Payment failures must be escalated — automated recovery risks double-charges or transaction loss."
            elif "auth" in comp_lower:
                strategy_key = "rollback"
                root_cause   = "Auth service failure could indicate a config or credential change gone wrong."
                reasoning    = "Rollback restores the last known working auth config quickly and safely."
            elif has_downstream and open_failures > 2:
                strategy_key = "isolate"
                root_cause   = "Repeated failures in a component with dependents risk cascading impact."
                reasoning    = "Circuit breaker isolation stops the failure from propagating downstream while the root cause is investigated."
            else:
                strategy_key = "escalate" if severity >= 4 else "restart"
                root_cause   = "Unrecognised error pattern requiring investigation."
                reasoning    = "No matching error pattern found. Escalating to a human for high-severity issues, restarting for lower severity."

        # ── Confidence calculation ──
        base_conf = HEALING_STRATEGIES[strategy_key]["base_probability"]
        if failure_count > 5:
            base_conf -= 0.08
        if open_failures > 2:
            base_conf -= 0.05
        if severity >= 4:
            base_conf -= 0.05
        confidence = round(max(0.35, min(0.97, base_conf)), 2)

        return {
            "strategy":      strategy_key,
            "strategy_name": HEALING_STRATEGIES[strategy_key]["name"],
            "confidence":    confidence,
            "root_cause":    root_cause,
            "reasoning":     reasoning,
            "component":     component,
            "error":         error,
            "severity":      severity,
        }

    def reliability_score(self):
        logs = self.get_logs()
        if not logs:
            return {"message": "No data available yet."}
        now = datetime.now()
        component_scores = {}
        for log in logs:
            comp = log["component"]
            try:
                ts = datetime.strptime(log["timestamp"], "%Y-%m-%d %H:%M:%S")
                decay = max(0.2, 1.0 - ((now - ts).days / 30))
            except (ValueError, TypeError):
                decay = 1.0
            status_factor = 0.3 if log["status"] == "Closed" else 1.0
            component_scores[comp] = component_scores.get(comp, 0) + log["severity"] * 2 * decay * status_factor
        reliability = {comp: round(max(0, min(100, 100 - score)), 1) for comp, score in component_scores.items()}
        weakest = min(reliability, key=reliability.get)
        avg = round(sum(reliability.values()) / len(reliability), 1)
        return {
            "reliability_scores": reliability, "weakest_component": weakest,
            "system_avg_reliability": avg,
            "overall_health": "Healthy" if avg >= 80 else "Degraded" if avg >= 50 else "Critical",
        }