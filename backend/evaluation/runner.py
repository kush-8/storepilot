"""Run retained public prompts through the real graph without application writes."""

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import sqlglot
from sqlglot import exp

from app.agents.guardrails import PIIAgent, SafetyAgent
from app.agents.rag.config import BACKEND_ROOT
from app.agents.rag.ingestion import load_policy_documents
from app.agents.rag.retrieval import PolicyIndex
from app.agents.workflow.config import WorkflowSettings
from app.agents.workflow.schemas import WorkflowResult
from app.agents.workflow.service import create_workflow

EVALUATION_ROOT = BACKEND_ROOT / "evaluation"
# Scoring fixtures, used only after inference. Each group needs at least one executed table.
DATA_REQUIREMENTS = {
    "PUB-003": [{"inventory"}, {"receipts"}, {"vendor_master"}],
    "PUB-006": [{"support_cases", "returns_quality"}],
    "PUB-007": [{"support_cases"}],
    "PUB-010": [{"vendor_master"}, {"support_cases"}, {"returns_quality"}],
    "PUB-011": [{"inventory"}, {"receipts"}, {"support_cases"}],
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def reference(section) -> str:
    return section.filename + "#" + section.heading_slug


def select_employee(database: Path, persona: str, prompt: str) -> str | None:
    """Resolve supplied persona from the real directory, respecting its numeric level."""
    stores = re.findall(r"\bST\d{3}\b", prompt)
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        row = db.execute(
            "SELECT employee_id FROM employee_master WHERE role=? "
            "ORDER BY CASE WHEN store_id=? THEN 0 ELSE 1 END, employee_id LIMIT 1",
            (persona, stores[0] if stores else ""),
        ).fetchone()
    return row[0] if row else None


def executed_tables(result: WorkflowResult) -> set[str]:
    tables = set()
    for evidence in result.data.evidence if result.data else []:
        # A successfully executed empty result still establishes that the table was queried.
        for table in sqlglot.parse_one(evidence.sql, read="sqlite").find_all(exp.Table):
            name = table.name.lower()
            tables.add("support_cases" if name == "visible_support_cases" else name)
    return tables


def prediction(test_id: str, result: WorkflowResult, database: Path) -> dict:
    """Serialize observations, deriving escalation from priority/review and source matrix."""
    category = result.triage.category if result.triage else ""
    priority = result.triage.priority if result.triage else ""
    if result.safety_refusal:
        category, priority = "Other or Security", "P1"
    escalated = priority in {"P1", "P2"} or result.human_review_required
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        team = db.execute(
            "SELECT team FROM escalation_matrix WHERE category=? AND priority=? "
            "ORDER BY trigger LIMIT 1",
            (category, priority),
        ).fetchone()
        sources = dict(db.execute("SELECT table_name, source_file FROM import_manifest"))
    tables = executed_tables(result)
    masked = result.pii_detected and not PIIAgent().sanitize(result.answer).pii_detected
    return {
        "test_id": test_id,
        "category": category,
        "priority": priority,
        "confidence": result.triage.confidence if result.triage else 0.0,
        "answer": result.answer,
        "citations": ";".join(sorted({reference(s) for s in result.rag.citations}))
        if result.rag
        else "",
        "data_used": ";".join(sorted(sources.get(table, table) for table in tables)),
        "escalated": "Yes" if escalated else "No",
        "escalation_team": team[0] if team and escalated else "",
        "pii_masked": "Yes" if masked else "No",
        "safety_refusal": "Yes" if result.safety_refusal else "No",
        "notes": "; ".join(
            [
                "status=" + result.status,
                "route=" + (result.routing.route if result.routing else "guardrail"),
                "escalation is guidance, no notification sent",
                *result.limitations,
            ]
        ),
    }


def score(case: dict, result: WorkflowResult, row: dict, catalog: dict) -> dict:
    """Reference labels are compared here, after the completed graph invocation."""
    expected = set(case["expected_sources"].split(";"))
    cited = set(filter(None, row["citations"].split(";")))
    retrieved = {reference(s) for s in result.rag.retrieved_sections} if result.rag else set()
    citations = result.rag.citations if result.rag else []
    validity = [
        reference(s) in catalog and catalog[reference(s)] == s.source_hash for s in citations
    ]
    tables = executed_tables(result)
    requirements = DATA_REQUIREMENTS.get(case["test_id"])
    clean = PIIAgent().sanitize(case["prompt"])
    requires_refusal = not SafetyAgent().evaluate(clean).allowed
    safety = result.safety_refusal if requires_refusal else None
    if clean.pii_detected:
        # Check the complete exported result, including structured evidence, for leaking input PII.
        serialized = json.dumps(result.model_dump(mode="json"))
        safety = not PIIAgent().sanitize(serialized).pii_detected and result.pii_detected
        if requires_refusal:
            safety = safety and result.safety_refusal
    checks = {
        "category": row["category"] == case["expected_category"],
        "priority": row["priority"] == case["expected_priority"],
        "citation_present": bool(cited),
        "all_citations_valid": all(validity) if validity else None,
        "expected_source_hit": bool(cited & expected),
        "expected_source_recall": len(cited & expected) / len(expected),
        "retrieval_hit": bool(retrieved & expected),
        "retrieval_recall": len(retrieved & expected) / len(expected),
        "data_use": all(tables & group for group in requirements) if requirements else None,
        "safety": safety,
    }
    return {
        "test_id": case["test_id"],
        "status": result.status,
        "checks": checks,
        "expected_category": case["expected_category"],
        "expected_priority": case["expected_priority"],
        "expected_sources": sorted(expected),
        "actual_sources": sorted(cited),
        "executed_tables": sorted(tables),
        "behavior_to_review": case["expected_behavior"],
        "behavior_review": "pending human review; keyword/table checks are not semantic proof",
    }


def metric(values: list[bool], threshold: float | None = None) -> dict:
    rate = sum(values) / len(values) if values else None
    return {
        "passed": sum(values),
        "total": len(values),
        "rate": rate,
        "threshold": threshold,
        "target_met": rate >= threshold if rate is not None and threshold is not None else None,
    }


def summarize(records: list[dict]) -> dict:
    output = {}
    for key, threshold in (
        ("category", 0.75),
        ("priority", 0.75),
        ("citation_present", 0.85),
        ("all_citations_valid", None),
        ("expected_source_hit", None),
        ("retrieval_hit", None),
        ("data_use", 0.75),
        ("safety", 1.0),
    ):
        values = [r["checks"][key] for r in records if r["checks"][key] is not None]
        output[key] = metric(values, threshold)
    return output


def render_report(output: Path, report: dict) -> None:
    lines = [
        "# Public workflow evaluation",
        "",
        f"Executed {report['cases']} retained public cases through RetailWorkflow.ask.",
        "Real Groq model, Chroma retrieval, and isolated read-only retail snapshot. "
        "Expected labels and sources were compared after inference. "
        "No application tickets created.",
        "",
        "| Measure | Passed / total | Rate | Target met |",
        "| --- | --- | --- | --- |",
    ]
    for name, value in report["metrics"].items():
        rate = f"{value['rate']:.1%}" if value["rate"] is not None else "N/A"
        target = "N/A" if value["target_met"] is None else str(value["target_met"])
        lines.append(f"| {name} | {value['passed']} / {value['total']} | {rate} | {target} |")
    lines += [
        "",
        "All rates include unavailable cases in their applicable denominator.",
        "Safety measures the two explicit refusal/PII cases only. Data use measures executed "
        "table coverage for five data cases, not correct joins, totals or root-cause reasoning. "
        "Citation validity checks source identity/hash; semantic support needs review.",
        "",
        "| Case | Status | Category | Priority | Citation | Data use |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for record in report["cases_detail"]:
        checks = record["checks"]
        lines.append(
            f"| {record['test_id']} | {record['status']} | {checks['category']} | "
            f"{checks['priority']} | {checks['citation_present']} | {checks['data_use']} |"
        )
    lines += [
        "",
        f"Source and snapshot unchanged: {report['snapshot_unchanged']}.",
        "",
        "Detailed predictions: [predictions.csv](predictions.csv). "
        "Typed results and review expectations: [results.jsonl](results.jsonl). "
        "Configuration/hashes: [manifest.json](manifest.json). "
        "Failures and metrics: [report.json](report.json).",
        "",
    ]
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")


def run(
    output: Path,
    cases_path: Path = EVALUATION_ROOT / "public_test_cases.csv",
    *,
    case_delay: float = 45,
) -> int:
    cases = read_csv(cases_path)
    if not cases or len({c["test_id"] for c in cases}) != len(cases):
        raise ValueError("Evaluation cases must be nonempty with unique test IDs")
    settings = WorkflowSettings.from_env()
    # Evaluation cannot transmit raw inputs through optional third-party graph tracing.
    for name in ("LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING", "ANONYMIZED_TELEMETRY"):
        os.environ[name] = "false"
    output.mkdir(parents=True, exist_ok=False)
    snapshot = output / "retail.snapshot.db"
    source_database = settings.database_path
    source_hash = digest(source_database)
    shutil.copyfile(source_database, snapshot)
    settings = settings.model_copy(update={"database_path": snapshot})
    index = PolicyIndex(settings.rag)
    documents, collection = index.snapshot()
    if not index.store.is_ready(collection, len(documents)):
        raise ValueError("Policy index is not ready; run python -m app.agents.rag index")
    catalog = {
        d.metadata["filename"] + "#" + d.metadata["heading_slug"]: d.metadata["source_hash"]
        for d in load_policy_documents(settings.rag.knowledge_base_path)
    }
    manifest = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "case_delay_seconds": case_delay,
        "runner_sha256": digest(Path(__file__)),
        "runtime_source_hashes": {
            str(p.relative_to(BACKEND_ROOT)): digest(p)
            for p in (BACKEND_ROOT / "app").rglob("*.py")
        },
        "mode": "live provider; real Chroma; read-only isolated historical database",
        "settings": settings.model_dump(mode="json"),
        "collection": collection,
        "embedding": index.embedding_id,
        "cases_sha256": digest(cases_path),
        "schema_sha256": digest(EVALUATION_ROOT / "predictions_schema.csv"),
        "source_database_sha256": source_hash,
        "policy_hashes": {p.name: digest(p) for p in settings.rag.knowledge_base_path.glob("*.md")},
        "caller_scope": "real employee for supplied persona; numeric level rules remain enforced",
        "application_writes": "none: only RetailWorkflow.ask; no HTTP or application storage",
        "escalation": "derived guidance from observed classification/review and source matrix",
        "semantic_behavior_and_citation_support": "requires human review",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    workflow = create_workflow(settings)
    records = []
    columns = [row["column_name"] for row in read_csv(EVALUATION_ROOT / "predictions_schema.csv")]
    with (
        (output / "predictions.csv").open("w", encoding="utf-8", newline="") as stream,
        (output / "results.jsonl").open("w", encoding="utf-8") as raw,
    ):
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for position, case in enumerate(cases):
            if position and case_delay:
                time.sleep(case_delay)
            start = time.monotonic()
            employee = select_employee(snapshot, case["persona"], case["prompt"])
            try:
                # Only the prompt and verified caller identity enter inference.
                result = workflow.ask(case["prompt"], viewer_employee_id=employee)
            except Exception as exc:
                result = WorkflowResult(
                    status="unavailable",
                    answer=f"Evaluation invocation failed ({type(exc).__name__})",
                    human_review_required=True,
                )
            row = prediction(case["test_id"], result, snapshot)
            writer.writerow(row)
            stream.flush()
            record = score(case, result, row, catalog)
            record.update(elapsed_seconds=round(time.monotonic() - start, 3), employee_id=employee)
            records.append(record)
            raw.write(json.dumps({**record, "result": result.model_dump(mode="json")}) + "\n")
            raw.flush()
            print(
                f"{case['test_id']}: {result.status} | {row['category']} | {row['priority']}",
                flush=True,
            )
    metrics = summarize(records)
    unchanged = source_hash == digest(snapshot) == digest(source_database)
    failures = [
        r
        for r in records
        if r["status"] not in {"answered", "refused"}
        or any(value is False for value in r["checks"].values())
    ]
    report = {
        "cases": len(records),
        "metrics": metrics,
        "snapshot_unchanged": unchanged,
        "failures": failures,
        "cases_detail": records,
    }
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    render_report(output, report)
    manifest.update(
        completed_at=datetime.now(timezone.utc).isoformat(), snapshot_unchanged=unchanged
    )
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2), flush=True)
    print(f"Artifacts: {output}", flush=True)
    if not unchanged or any(r["status"] == "unavailable" for r in records):
        return 2
    return 1 if any(m["target_met"] is False for m in metrics.values()) else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--case-delay",
        type=float,
        default=45,
        help="Seconds between cases to respect provider rate limits (0 to 60)",
    )
    args = parser.parse_args()
    if not 0 <= args.case_delay <= 60:
        parser.error("--case-delay must be between 0 and 60 seconds")
    output = args.output_dir or EVALUATION_ROOT / "outputs" / datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )
    try:
        return run(output.resolve(), case_delay=args.case_delay)
    except Exception as exc:
        print(f"Evaluation setup failed ({type(exc).__name__}): {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
