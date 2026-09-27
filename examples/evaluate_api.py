"""Record five real HTTP assessments and their full outputs for a reproducible phase-6 review.

Start the API separately before running this script. These are structured-form
requests, not simulated LLM extractions; no extractor, graph, or model is mocked.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def check_result(case: dict, status: int, body: dict) -> list[str]:
    """Compare live observations to independently specified expected remedies and uncertainty."""
    expected = case["expected"]
    result = body.get("eligibility") or {}
    checks = {
        "HTTP 200": status == 200,
        "response status": body.get("status") == expected["status"],
        "eligibility": result.get("eligible") == expected["eligible"],
        "cash amount": result.get("compensation_amount") == expected["amount"],
        "disclaimer": "This is not legal advice" in body.get("disclaimer", ""),
    }
    if "currency" in expected:
        checks["currency"] = result.get("compensation_currency") == expected["currency"]
    if "refund_eligible" in expected:
        checks["refund eligibility"] = result.get("refund_eligible") == expected["refund_eligible"]
    if expected.get("letter_contains"):
        checks["letter remedy"] = expected["letter_contains"] in (body.get("claim_letter") or "")
    if expected.get("letter_absent"):
        checks["no premature letter"] = body.get("claim_letter") is None
    if expected.get("question_contains"):
        checks["follow-up"] = any(
            expected["question_contains"] in q for q in body.get("questions", [])
        )
    return [name for name, passed in checks.items() if not passed]


def json_block(value: object) -> str:
    """Preserve nulls and returned fields so the report exposes omissions."""
    return "```json\n" + json.dumps(value, indent=2, ensure_ascii=False) + "\n```"


def write_report(records: dict, directory: Path) -> None:
    """Save raw responses plus readable letters, so the user can inspect actual run evidence."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "phase6_api_results.json").write_text(
        json.dumps(records, indent=2, ensure_ascii=False) + "\n"
    )
    lines = [
        "# Phase 6 — actual local API evaluation",
        "",
        f"Run: {records['run_at']}",
        "",
        f"API: `{records['api_url']}`. No graph, rules, or prediction mocks.",
        "",
        "Inputs use the structured-form contract. Returned `collected_facts` are validated "
        "form facts, **not LLM-extracted facts**. Live narrative extraction is not verified. "
        "The missing-key probe is explicit opt-in and should only run with no key configured.",
        "",
        "## Active model",
        "",
        json_block(records["model_status"]),
    ]
    for item in records["scenarios"]:
        body = item["response"]
        lines += [
            "",
            f"## {item['title']}",
            "",
            f"HTTP {item['http_status']} — "
            f"{'PASS' if not item['failures'] else 'FAIL: ' + ', '.join(item['failures'])}",
            "",
            item["why"],
            "",
            "### Input sent",
            "",
            json_block(item["request"]),
            "",
            "### Structured facts returned",
            "",
            json_block(body.get("collected_facts")),
            "",
            "### Rules-engine results (including reasoning)",
            "",
            json_block(
                {
                    "primary": body.get("eligibility"),
                    "additional": body.get("additional_assessments"),
                }
            ),
            "",
            "### Final response and letter",
            "",
            json_block(
                {
                    key: body.get(key)
                    for key in ["status", "questions", "warnings", "steps", "disclaimer"]
                }
            ),
            "",
            "```text\n" + (body.get("claim_letter") or "No letter drafted.") + "\n```",
        ]
    lines += ["", "## Error handling and prediction probes", ""]
    for probe in records["probes"]:
        lines += [f"### {probe['name']}", "", json_block(probe), ""]
    lines += [
        "## Legal boundary references",
        "",
        "The exactly-three-hour test uses the inclusive final-arrival threshold in "
        "[European Commission guidance](https://europa.eu/youreurope/citizens/travel/"
        "passenger-rights/air/index_en.htm). The DOT tier and January 22, 2025 cap change "
        "are in [14 CFR 250.5 and its effective-date note](https://www.govinfo.gov/content/"
        "pkg/CFR-2025-title14-vol4/pdf/CFR-2025-title14-vol4-sec250-5.pdf). Refund conditions "
        "are in [14 CFR 260.6](https://www.ecfr.gov/current/title-14/chapter-II/subchapter-A/"
        "part-260/section-260.6).",
        "",
        "This is not legal advice.",
        "",
    ]
    (directory / "phase6_evaluation.md").write_text("\n".join(lines))


def main() -> None:
    """Evaluate an already-running service; fail the command if any expected behavior differs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports")
    parser.add_argument(
        "--check-missing-key",
        action="store_true",
        help="Only use against an API configured without an LLM key.",
    )
    args = parser.parse_args()
    cases = json.loads((ROOT / "examples/phase6_scenarios.json").read_text())
    records = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "api_url": args.api_url,
        "scenarios": [],
        "probes": [],
    }
    failures = []
    with httpx.Client(base_url=args.api_url, timeout=90) as client:
        source = client.get("/model-status")
        source.raise_for_status()
        records["model_status"] = source.json()
        for case in cases:
            response = client.post("/assess", json=case["request"])
            body = response.json()
            failed = check_result(case, response.status_code, body)
            failures.extend(f"{case['id']}: {name}" for name in failed)
            records["scenarios"].append(
                {**case, "http_status": response.status_code, "response": body, "failures": failed}
            )
            result = body.get("eligibility") or {}
            print(
                json.dumps(
                    {
                        "id": case["id"],
                        "http": response.status_code,
                        "status": body.get("status"),
                        "eligible": result.get("eligible"),
                        "amount": result.get("compensation_amount"),
                        "refund": result.get("refund_eligible"),
                        "questions": body.get("questions"),
                        "failures": failed,
                    }
                )
            )
        unknown = json.loads(json.dumps(cases[4]["request"]))
        unknown["disruption"]["flight"]["departure_airport"] = "ZZZ"
        prediction = {**cases[2]["request"], "want_prediction": True}
        probes = [
            ("malformed JSON", "{invalid", 422, "error"),
            ("unknown airport", unknown, 200, "review_required"),
            ("saved model prediction", prediction, 200, "complete"),
        ]
        if args.check_missing_key:
            probes.append(("missing LLM key", {"text": "My flight was delayed."}, 200, "error"))
        for name, payload, expected_http, expected_status in probes:
            response = (
                client.post(
                    "/assess", content=payload, headers={"Content-Type": "application/json"}
                )
                if isinstance(payload, str)
                else client.post("/assess", json=payload)
            )
            body = response.json()
            passed = (
                response.status_code == expected_http
                and body.get("status") == expected_status
                and "This is not legal advice" in body.get("disclaimer", "")
            )
            if name == "saved model prediction":
                passed = passed and (body.get("delay_prediction") or {}).get("data_source") == "bts"
            if name == "unknown airport":
                passed = passed and body.get("claim_letter") is None
            if name == "missing LLM key":
                passed = passed and any("No API key" in w for w in body.get("warnings", []))
            if not passed:
                failures.append(name)
            records["probes"].append(
                {
                    "name": name,
                    "request": payload,
                    "http_status": response.status_code,
                    "response": body,
                    "passed": passed,
                }
            )
            print(
                json.dumps(
                    {
                        "probe": name,
                        "http": response.status_code,
                        "status": body.get("status"),
                        "passed": passed,
                    }
                )
            )
    records["failures"] = failures
    write_report(records, args.output_dir)
    print(f"Full inputs, facts, reasons and letters: {args.output_dir / 'phase6_evaluation.md'}")
    print("This is not legal advice.")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
