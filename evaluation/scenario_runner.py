"""Automated runner for the 12 clinical decision-support scenarios from the Project Guide."""
import json
import logging
import sys
import time
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from orchestration.graph import workflow
from validators.output_validator import OutputValidator

logger = logging.getLogger("healthcare_agentic_ai.evaluation.scenarios")
SCENARIO_FILE = ROOT / "evaluation" / "clinical_scenarios.json"
REPORT_FILE = ROOT / "evaluation" / "scenario_report.json"


def run_all_scenarios():
    if not SCENARIO_FILE.is_file():
        print(f"Error: {SCENARIO_FILE} does not exist.")
        return 1

    scenarios = json.loads(SCENARIO_FILE.read_text(encoding="utf-8"))
    print(f"Loaded {len(scenarios)} clinical scenarios for validation.\n")

    results = []
    passed_count = 0

    for sc in scenarios:
        sc_id = sc["id"]
        title = sc["title"]
        print(f"--- Running {sc_id}: {title} ---")

        t0 = time.perf_counter()
        initial_state = {
            "case_id": f"SCENARIO-{sc_id}",
            "question": sc["question"],
            "patient_context": sc.get("patient_context", {}),
            "workflow_steps": [],
            "retry_count": 0,
        }

        try:
            output = workflow.invoke(initial_state, config={"recursion_limit": 20})
            duration = round(time.perf_counter() - t0, 3)

            # Check expected criteria
            expected = sc.get("expected", {})
            test_passed = True
            reasons = []

            if expected.get("case_status") and output.get("case_status") != expected["case_status"]:
                test_passed = False
                reasons.append(f"case_status mismatch: expected {expected['case_status']}, got {output.get('case_status')}")

            if expected.get("scope_status") and output.get("scope_status") != expected["scope_status"]:
                test_passed = False
                reasons.append(f"scope_status mismatch: expected {expected['scope_status']}, got {output.get('scope_status')}")

            if expected.get("missing_information_contains"):
                target = expected["missing_information_contains"]
                if target not in output.get("missing_information", []):
                    test_passed = False
                    reasons.append(f"missing_information did not contain '{target}'")

            if test_passed:
                passed_count += 1
                status_str = "PASSED"
            else:
                status_str = "FAILED"

            print(f"Result: {status_str} ({duration}s)")
            if reasons:
                for r in reasons:
                    print(f"  - {r}")

            results.append({
                "id": sc_id,
                "title": title,
                "status": status_str,
                "duration_seconds": duration,
                "workflow_status": output.get("workflow_status"),
                "case_status": output.get("case_status"),
                "request_type": output.get("request_type"),
                "validation_passed": output.get("validation", {}).get("passed", False),
                "reasons": reasons,
            })

        except Exception as exc:
            duration = round(time.perf_counter() - t0, 3)
            print(f"Result: ERROR ({exc})")
            results.append({
                "id": sc_id,
                "title": title,
                "status": "ERROR",
                "duration_seconds": duration,
                "error": str(exc),
            })

    summary = {
        "timestamp": time.time(),
        "total_scenarios": len(scenarios),
        "passed": passed_count,
        "failed": len(scenarios) - passed_count,
        "pass_rate": round((passed_count / len(scenarios)) * 100, 2) if scenarios else 0.0,
        "scenarios": results,
    }

    REPORT_FILE.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n==========================================")
    print(f"Completed: {passed_count}/{len(scenarios)} passed ({summary['pass_rate']}%)")
    print(f"Report saved to: {REPORT_FILE}")
    print(f"==========================================")
    return 0 if passed_count == len(scenarios) else 1


if __name__ == "__main__":
    sys.exit(run_all_scenarios())
