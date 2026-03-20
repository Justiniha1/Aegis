import json
import importlib
from datetime import datetime
from pathlib import Path

from backend.core.config_loader import DQFConfig, TestDefinition
from backend.core.database_connector import DatabaseConnector

RESULTS_DIR = Path(__file__).parent.parent.parent / "data" / "processed"

STATUS_ICONS = {
    "PASSED": "PASS",
    "FAILED": "FAIL",
    "SKIPPED": "SKIP",
    "ERROR": "ERR ",
}

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


class TestEngine:
    def __init__(self, config: DQFConfig):
        self.config = config
        self._connectors: dict[str, DatabaseConnector] = {}

    def _get_connector(self, profile_name: str) -> DatabaseConnector | None:
        if profile_name not in self.config.connections:
            return None
        if profile_name not in self._connectors:
            self._connectors[profile_name] = DatabaseConnector(
                self.config.connections[profile_name]
            )
        return self._connectors[profile_name]

    def run(self) -> list[dict]:
        results = []
        enabled = [t for t in self.config.tests if t.enabled]
        total = len(enabled)
        print(f"\nRunning Data Quality Tests ({total} enabled)\n")

        for i, test_def in enumerate(enabled, 1):
            label = f"[{i}/{total}] {test_def.name}"
            result = self._run_one(test_def, label)
            results.append(result)

        return results

    def _run_one(self, test_def: TestDefinition, label: str) -> dict:
        connector = self._get_connector(test_def.profile)
        if connector is None:
            result = {
                "test_id": test_def.test_id,
                "name": test_def.name,
                "type": test_def.type,
                "status": "SKIPPED",
                "severity": test_def.severity,
                "metrics": {},
                "message": (
                    f"Profile '{test_def.profile}' not found in database_connection.yaml"
                ),
            }
            icon = STATUS_ICONS["SKIPPED"]
            print(f"  {icon} {label:<55} SKIPPED  ({result['message']})")
            return result

        try:
            module = importlib.import_module(
                f"backend.tests.builtin.{test_def.type}"
            )
            test_dict = dict(test_def.raw)
            test_dict["_test_id"] = test_def.test_id
            result = module.run(connector, test_dict)
        except ModuleNotFoundError:
            result = {
                "test_id": test_def.test_id,
                "name": test_def.name,
                "type": test_def.type,
                "status": "ERROR",
                "severity": test_def.severity,
                "metrics": {},
                "message": f"Test type '{test_def.type}' is not implemented yet",
            }
        except Exception as e:
            result = {
                "test_id": test_def.test_id,
                "name": test_def.name,
                "type": test_def.type,
                "status": "ERROR",
                "severity": test_def.severity,
                "metrics": {},
                "message": str(e),
            }

        icon = STATUS_ICONS.get(result["status"], "????")
        status = result["status"]
        sev = f"[{result['severity']}]" if status in ("FAILED", "ERROR") else ""
        print(f"  {icon} {label:<55} {status:<8} {sev}")
        if status in ("FAILED", "ERROR"):
            print(f"       > {result['message']}")

        return result

    def print_summary(self, results: list[dict]) -> None:
        counts = {"PASSED": 0, "FAILED": 0, "ERROR": 0, "SKIPPED": 0}
        for r in results:
            counts[r.get("status", "ERROR")] += 1

        total = len(results)
        print("\n" + "-" * 65)
        print(
            f"Results: {total} tests -- "
            f"{counts['PASSED']} passed  "
            f"{counts['FAILED']} failed  "
            f"{counts['ERROR']} errors  "
            f"{counts['SKIPPED']} skipped"
        )

        # Show critical/high failures first
        failures = [
            r for r in results if r["status"] in ("FAILED", "ERROR")
        ]
        if failures:
            failures.sort(key=lambda r: SEVERITY_ORDER.get(r.get("severity", "MEDIUM"), 2))
            print("\nIssues to address:")
            for r in failures:
                print(f"   [{r['severity']}] {r['name']}: {r['message']}")

    def save_results(self, results: list[dict]) -> Path:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = RESULTS_DIR / f"test_results_{timestamp}.json"

        payload = {
            "run_timestamp": datetime.now().isoformat(),
            "engine": self.config.engine.engine,
            "summary": {
                "total": len(results),
                "passed": sum(1 for r in results if r["status"] == "PASSED"),
                "failed": sum(1 for r in results if r["status"] == "FAILED"),
                "errors": sum(1 for r in results if r["status"] == "ERROR"),
                "skipped": sum(1 for r in results if r["status"] == "SKIPPED"),
            },
            "results": results,
        }

        with open(out_path, "w") as f:
            json.dump(payload, f, indent=2, default=str)

        print(f"\nResults saved to: {out_path}")
        return out_path
