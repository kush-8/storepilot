"""Evaluation integrity: observed evidence, scoped identities and no answer leakage."""

import csv
import json
from pathlib import Path
from types import SimpleNamespace

from app.agents.data.schemas import DataEvidence, DataResult
from app.agents.rag.schemas import RagResult
from app.agents.workflow.schemas import WorkflowResult
from evaluation import runner
from tests.agent_fakes import offline_workflow


def test_executed_sources_come_from_sql_not_expected_case_or_query_label():
    result = WorkflowResult(
        status="answered",
        answer="Evidence",
        data=DataResult(
            status="answered",
            summary="Evidence",
            evidence=[
                DataEvidence(
                    evidence_id="observed",
                    query="case_summary",
                    rows=[],
                    sql="SELECT COUNT(*) FROM visible_support_cases",
                ),
                DataEvidence(
                    evidence_id="observed2",
                    query="receipts",
                    rows=[],
                    sql="SELECT vendor_id FROM receipts JOIN vendor_master USING(vendor_id)",
                ),
            ],
        ),
    )
    assert runner.executed_tables(result) == {"support_cases", "receipts", "vendor_master"}


def test_security_prediction_uses_guardrail_without_expected_labels():
    result = WorkflowResult(
        status="refused", answer="Refused", safety_refusal=True, human_review_required=True
    )
    row = runner.prediction("unseen-case", result, runner.BACKEND_ROOT / "database/retail.db")
    assert row["category"] == "Other or Security"
    assert row["priority"] == "P1"
    assert row["escalation_team"] == "Security"
    assert row["citations"] == row["data_used"] == ""


def test_missing_citations_are_not_counted_as_valid_or_as_retrieval_hits():
    case = runner.read_csv(runner.EVALUATION_ROOT / "public_test_cases.csv")[0]
    result = WorkflowResult(
        status="unavailable",
        answer="Unavailable",
        rag=RagResult(status="model_unavailable", answer="Unavailable"),
    )
    row = runner.prediction(case["test_id"], result, runner.BACKEND_ROOT / "database/retail.db")
    record = runner.score(case, result, row, {})
    metrics = runner.summarize([record])
    assert metrics["all_citations_valid"]["total"] == 0
    assert metrics["retrieval_hit"]["passed"] == 0
    assert metrics["category"]["passed"] == 0


def test_runner_keeps_labels_out_of_inference_and_does_not_write_source(tmp_path, monkeypatch):
    cases_path = tmp_path / "cases.csv"
    case = runner.read_csv(runner.EVALUATION_ROOT / "public_test_cases.csv")[7]
    case.update(expected_category="DO-NOT-SEND-THIS-EXPECTED-LABEL")
    with cases_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=case.keys())
        writer.writeheader()
        writer.writerow(case)
    calls = []

    def create(settings):
        real = offline_workflow(settings.database_path)

        def ask(question, **kwargs):
            calls.append((question, kwargs))
            return real.workflow.ask(question, **kwargs)

        return SimpleNamespace(ask=ask)

    monkeypatch.setattr(runner, "create_workflow", create)
    monkeypatch.setattr(
        runner,
        "PolicyIndex",
        lambda settings: SimpleNamespace(
            snapshot=lambda: ([], "test-index"),
            store=SimpleNamespace(is_ready=lambda *args: True),
            embedding_id="test-only",
        ),
    )
    source = runner.BACKEND_ROOT / "database/retail.db"
    application = runner.BACKEND_ROOT / "database/storepilot.db"
    before = runner.digest(source)
    app_before = runner.digest(application) if application.exists() else None
    output = tmp_path / "output"
    assert runner.run(output, cases_path) == 1
    assert calls == [(case["prompt"], {"viewer_employee_id": None})]
    assert runner.digest(source) == before
    assert (runner.digest(application) if application.exists() else None) == app_before
    report = json.loads((output / "report.json").read_text())
    assert report["snapshot_unchanged"]
    with (output / "predictions.csv").open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        assert reader.fieldnames == [
            r["column_name"]
            for r in runner.read_csv(runner.EVALUATION_ROOT / "predictions_schema.csv")
        ]
        assert next(reader)["category"] == "Other or Security"
    manifest = (output / "manifest.json").read_text()
    assert "groq_api_key" not in manifest


def test_persona_resolution_preserves_supplied_store_and_directory_level():
    database = runner.BACKEND_ROOT / "database/retail.db"
    import sqlite3
    from contextlib import closing

    with closing(sqlite3.connect(Path(database).resolve().as_uri() + "?mode=ro", uri=True)) as db:
        store = db.execute(
            "SELECT store_id FROM employee_master WHERE role='Store Manager' "
            "ORDER BY employee_id LIMIT 1"
        ).fetchone()[0]
        employee = runner.select_employee(
            database, "Store Manager", f"Registers at {store} are down"
        )
        assert employee is not None
        assert db.execute(
            "SELECT role, store_id, escalation_level FROM employee_master WHERE employee_id=?",
            (employee,),
        ).fetchone() == (
            "Store Manager",
            store,
            4,
        )
    assert runner.select_employee(database, "Unknown", "") is None
