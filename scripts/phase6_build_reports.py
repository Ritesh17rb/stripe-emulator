import csv
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = ROOT / "artifacts" / "logs"
REPORTS_DIR = ROOT / "artifacts" / "reports"
CASES_FILE = ROOT / "test-cases" / "generated" / "payment_intents_cases.json"
SCOPE_FILE = ROOT / "docs" / "requirements" / "traceability_scope_core.csv"


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def build_pass_rate_report() -> dict:
    targets = ["stripe", "emulator"]
    summary = {"targets": {}, "combined": {}}
    total_cases = set()
    combined_passed = set()

    for target in targets:
        rows = load_jsonl(LOGS_DIR / f"latest_run_{target}.jsonl")
        by_case = defaultdict(list)
        for row in rows:
            by_case[row.get("case_id")].append(row)

        case_count = len(by_case)
        passed_cases = 0
        failed_cases = []
        for case_id, steps in by_case.items():
            total_cases.add(case_id)
            case_passed = all(step.get("passed", False) for step in steps)
            if case_passed:
                passed_cases += 1
                combined_passed.add((target, case_id))
            else:
                first_failure = next((step for step in steps if not step.get("passed", False)), None)
                failed_cases.append(
                    {
                        "case_id": case_id,
                        "failed_step_error": first_failure.get("error") if first_failure else "unknown",
                    }
                )

        pass_rate = round((passed_cases / case_count) * 100, 2) if case_count else 0.0
        summary["targets"][target] = {
            "case_count": case_count,
            "passed_cases": passed_cases,
            "failed_cases": case_count - passed_cases,
            "pass_rate_percent": pass_rate,
            "top_failures": failed_cases[:25],
        }

    total_target_cases = sum(summary["targets"][t]["case_count"] for t in targets)
    total_target_passed = sum(summary["targets"][t]["passed_cases"] for t in targets)
    combined_rate = round((total_target_passed / total_target_cases) * 100, 2) if total_target_cases else 0.0
    summary["combined"] = {
        "total_target_case_executions": total_target_cases,
        "total_target_passed": total_target_passed,
        "pass_rate_percent": combined_rate,
    }
    return summary


def build_coverage_report() -> dict:
    if not CASES_FILE.exists():
        return {"error": "missing cases file"}
    cases = json.loads(CASES_FILE.read_text(encoding="utf-8")).get("cases", [])
    covered_sentence_ids = set()
    for case in cases:
        for sentence_id in case.get("doc_refs", []):
            covered_sentence_ids.add(sentence_id)

    denominator = set()
    with SCOPE_FILE.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            denominator.add(row["sentence_id"])

    uncovered = sorted(list(denominator - covered_sentence_ids))
    coverage_percent = round((len(covered_sentence_ids & denominator) / len(denominator)) * 100, 2) if denominator else 0.0

    return {
        "scope_file": str(SCOPE_FILE.relative_to(ROOT)).replace("\\", "/"),
        "scope_sentence_count": len(denominator),
        "covered_sentence_count": len(covered_sentence_ids & denominator),
        "coverage_percent": coverage_percent,
        "uncovered_sentence_count": len(uncovered),
        "uncovered_sentence_ids_sample": uncovered[:200],
    }


def main() -> int:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    pass_report = build_pass_rate_report()
    coverage_report = build_coverage_report()

    pass_path = REPORTS_DIR / "pass_rate_summary.json"
    coverage_path = REPORTS_DIR / "doc_coverage_report.json"
    pass_path.write_text(json.dumps(pass_report, indent=2), encoding="utf-8")
    coverage_path.write_text(json.dumps(coverage_report, indent=2), encoding="utf-8")
    print(f"Wrote {pass_path}")
    print(f"Wrote {coverage_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

