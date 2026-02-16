import random
import time
from datetime import datetime
import requests


class FailureLogger:

    def __init__(self):
        self.logs = []

    # ---------------- LOG FAILURE ----------------
    def log_failure(self, component, severity, error, source="Manual"):
        log = {
            "component": component,
            "severity": severity,
            "error": error,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "Open",
            "source": source
        }
        self.logs.append(log)
        print("\nFailure recorded successfully\n")

    # ---------------- AUTO FAILURE SIMULATION ----------------
    def generate_simulated_failure(self):
        components = ["Database", "API", "Auth", "Payment", "Server"]
        errors = [
            "Connection timeout",
            "Memory leak detected",
            "Service unavailable",
            "High latency",
            "Authentication failed"
        ]

        component = random.choice(components)
        severity = random.randint(1, 5)
        error = random.choice(errors)

        self.log_failure(component, severity, error, source="Simulation")

    # ---------------- WEBSITE MONITORING ----------------
    def monitor_website(self, url):
        print(f"\nChecking website: {url}\n")

        try:
            response = requests.get(url, timeout=5)

            if response.status_code >= 500:
                self.log_failure(
                    "Website",
                    5,
                    f"Server error {response.status_code}",
                    source="Website Monitor"
                )

            elif response.status_code >= 400:
                self.log_failure(
                    "Website",
                    3,
                    f"Client error {response.status_code}",
                    source="Website Monitor"
                )

            else:
                print("Website is reachable and healthy\n")

        except requests.exceptions.Timeout:
            self.log_failure("Website", 5, "Timeout error", source="Website Monitor")

        except requests.exceptions.ConnectionError:
            self.log_failure("Website", 5, "Website unreachable", source="Website Monitor")

    # ---------------- VIEW LOGS ----------------
    def view_logs(self):
        if not self.logs:
            print("\nNo logs available\n")
            return

        print("\n========== FAILURE LOGS ==========")
        for i, log in enumerate(self.logs):
            print(f"\nLog Index: {i}")
            for key, value in log.items():
                print(f"{key}: {value}")

    # ---------------- SEARCH ----------------
    def search_component(self, component):
        results = [log for log in self.logs if log["component"].lower() == component.lower()]

        if not results:
            print("\nNo failures found\n")
            return

        print("\nSearch Results:")
        for log in results:
            print(log)

    # ---------------- UPDATE STATUS ----------------
    def update_status(self, index, status):
        try:
            self.logs[index]["status"] = status
            print("\nStatus updated successfully\n")
        except:
            print("\nInvalid index\n")

    # ---------------- FILTER SEVERITY ----------------
    def filter_severity(self, level):
        results = [log for log in self.logs if log["severity"] == level]

        if not results:
            print("\nNo logs with this severity\n")
            return

        print("\nFiltered Logs:")
        for log in results:
            print(log)

    # ---------------- COUNT ----------------
    def count_failures(self):
        print(f"\nTotal failures: {len(self.logs)}\n")


# ---------------- MENU SYSTEM ----------------

def main():
    logger = FailureLogger()

    while True:
        print("\n====== ASFIS Failure Logging System ======")
        print("1. Generate Simulated Failure")
        print("2. Log Failure Manually")
        print("3. Monitor Website")
        print("4. View Logs")
        print("5. Search by Component")
        print("6. Update Status")
        print("7. Filter by Severity")
        print("8. Count Failures")
        print("9. Exit")

        choice = input("Enter choice: ")

        if choice == "1":
            logger.generate_simulated_failure()

        elif choice == "2":
            component = input("Enter component: ")
            severity = int(input("Enter severity (1-5): "))
            error = input("Enter error message: ")
            logger.log_failure(component, severity, error)

        elif choice == "3":
            url = input("Enter website URL: ")
            logger.monitor_website(url)

        elif choice == "4":
            logger.view_logs()

        elif choice == "5":
            component = input("Enter component to search: ")
            logger.search_component(component)

        elif choice == "6":
            index = int(input("Enter log index: "))
            status = input("Enter new status (Open/Closed): ")
            logger.update_status(index, status)

        elif choice == "7":
            level = int(input("Enter severity level: "))
            logger.filter_severity(level)

        elif choice == "8":
            logger.count_failures()

        elif choice == "9":
            print("\nExiting system...\n")
            break

        else:
            print("\nInvalid choice\n")


if __name__ == "__main__":
    main()
