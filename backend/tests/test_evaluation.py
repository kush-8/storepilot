"""Backend-only evaluator: no expected-answer leakage or application writes."""

import csv
import hashlib
from copy import deepcopy

from tests.support import BACKEND, boundary


class RecordingWorkflow:
    def __init__(self):
        self.calls = []

    def invoke(self, payload):
        self.calls.append(deepcopy(payload))
        return {
            "category": "POS and Payments",
            "priority": "P3",
            "confidence": 0.9,
            "answer": "Test-only recommendation.",
            "citations": ["02_pos_pricing_returns_policy.md#pos-card-reader-runbook"],
            "data_used": [],
            "escalation": {"required": False, "team": None},
            "guardrails": {
                "pii_checked": True,
                "pii_detected": False,
                "safety_refusal": False,
                "human_review_required": False,
            },
        }


def run_once(databases, tmp_path):
    runner = boundary("app.evaluation.runner", "run_evaluation")
    workflow = RecordingWorkflow()
    cases = [
        {
            "test_id": "TEST-001",
            "persona": "Inventory Associate",
            "prompt": "Why is SKU1001 unavailable at ST002?",
            "expected_category": "Inventory and Replenishment",
            "expected_priority": "P2",
            "expected_sources": "03_inventory_replenishment_policy.md#stock-outs-and-replenishment",
            "expected_behavior": "EXPECTED_BEHAVIOUR_SENTINEL",
        }
    ]
    result = runner(
        cases=cases,
        workflow=workflow,
        output_dir=tmp_path / "outputs",
        retail_database=databases["retail"],
        application_database=databases["application"],
    )
    return result, workflow


def test_expected_answers_are_not_part_of_inference_input(databases, tmp_path):
    _, workflow = run_once(databases, tmp_path)
    assert len(workflow.calls) == 1
    payload = str(workflow.calls)
    for field in (
        "expected_category",
        "expected_priority",
        "expected_sources",
        "expected_behavior",
        "EXPECTED_BEHAVIOUR_SENTINEL",
    ):
        assert field not in payload


def test_evaluation_creates_no_tickets_or_source_changes(databases, tmp_path):
    before = {
        name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in databases.items()
    }
    run_once(databases, tmp_path)
    for name, path in databases.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == before[name]


def test_prediction_export_uses_exact_submission_columns_and_real_failures(databases, tmp_path):
    run_once(databases, tmp_path)
    path = tmp_path / "outputs" / "predictions.csv"
    assert path.is_file()
    with (BACKEND / "evaluation" / "predictions_schema.csv").open(newline="") as handle:
        expected_columns = [row["column_name"] for row in csv.DictReader(handle)]
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == expected_columns
        rows = list(reader)
    assert len(rows) == 1
    # The canned answer intentionally disagrees with labels; the runner must not copy them.
    assert rows[0]["category"] == "POS and Payments"
    assert rows[0]["priority"] == "P3"
    assert rows[0]["escalated"] == "No"


def test_metrics_use_actual_predictions_and_explicit_denominators(databases, tmp_path):
    result, _ = run_once(databases, tmp_path)
    assert result["metrics"]["category_accuracy"] == {"correct": 0, "total": 1, "rate": 0.0}
    assert result["metrics"]["priority_accuracy"] == {"correct": 0, "total": 1, "rate": 0.0}
    assert result["failures"]
