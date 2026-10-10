"""Offline routing, fan-out, grounding and scoped read-only data integration tests."""

import hashlib
import sqlite3
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from langchain_core.runnables import RunnableLambda
from pydantic import ValidationError

from app.agents.data.agent import DataAgent
from app.agents.data.repository import RetailRepository
from app.agents.data.schemas import DataResult
from app.agents.rag.config import BACKEND_ROOT
from app.agents.rag.schemas import RagResult
from app.agents.router.agent import RouterAgent
from app.agents.router.schemas import RouteDecision
from app.agents.triage.agent import TriageAgent
from app.agents.triage.schemas import Entities, TriageResult
from app.agents.workflow.input import prepare_question
from app.agents.workflow.nodes import WorkflowNodes
from app.agents.workflow.service import RetailWorkflow

ANCHOR = datetime.fromisoformat("2026-10-10T12:00:00+05:30")


def triage(**updates):
    return TriageResult(
        **{
            "summary": "What is the inventory for ST001 SKU1001?",
            "intent": "data_question",
            "category": "Inventory and Replenishment",
            "priority": "P4",
            "confidence": 0.95,
            "entities": Entities(store_id="ST001", sku="SKU1001"),
            **updates,
        }
    )


def workflow(route, *, classification=None, rag_result=None, data_result=None):
    classification = classification or triage()
    decision = RouteDecision(
        route=route,
        reason="Test evidence selection",
        queries=["inventory"] if route in {"data", "both"} else [],
        follow_up="Which SKU?" if route == "clarify" else None,
    )
    triage_model, router_model, rag_call, data = Mock(), Mock(), Mock(), Mock()
    triage_model.return_value, router_model.return_value = classification, decision
    rag_call.return_value = {"result": rag_result or RagResult(status="answered", answer="Policy")}
    data.invoke.return_value = data_result or DataResult(status="answered", summary="Inventory")
    nodes = WorkflowNodes(
        TriageAgent(RunnableLambda(triage_model)),
        RouterAgent(RunnableLambda(router_model)),
        SimpleNamespace(graph=RunnableLambda(rag_call)),
        data,
    )
    return RetailWorkflow(nodes), (triage_model, router_model, rag_call, data)


@pytest.mark.parametrize(
    "route,expected",
    [
        ("rag", (1, 0)),
        ("data", (0, 1)),
        ("both", (1, 1)),
    ],
)
def test_single_graph_routes_only_selected_agents_and_joins_once(route, expected):
    agent, spies = workflow(route)
    events = list(
        agent.graph.stream(
            {"question": "ST001 SKU1001 inventory", "viewer_employee_id": "E001"},
            stream_mode="updates",
        )
    )
    names = [name for event in events for name in event]
    assert names[:2] == ["triage_agent", "router_agent"]
    assert names.count("compose") == 1
    assert (spies[2].call_count, spies[3].invoke.call_count) == expected
    result = events[-1]["compose"]["result"]
    assert result.status == "answered"
    assert bool(result.rag) == bool(expected[0])
    assert bool(result.data) == bool(expected[1])
    assert "What is the inventory" in spies[1].call_args.args[0].to_messages()[-1].content
    if expected[1]:
        assert spies[3].invoke.call_args.args[2] == "E001"


@pytest.mark.parametrize(
    "route,status", [("clarify", "needs_clarification"), ("refuse", "refused")]
)
def test_non_evidence_routes_do_not_run_specialists(route, status):
    agent, spies = workflow(route)
    assert agent.ask("ST001 SKU1001").status == status
    spies[2].assert_not_called()
    spies[3].invoke.assert_not_called()


def test_policy_advice_cannot_be_routed_to_data_only():
    agent, _ = workflow("data", classification=triage(intent="recommendation"))
    assert agent.ask("ST001 SKU1001 what should we do?").routing.route == "both"


def test_urgent_incident_gets_policy_guidance_before_optional_clarification():
    agent, _ = workflow("clarify", classification=triage(intent="incident", priority="P1"))
    result = agent.ask("All registers are down")
    assert result.routing.route == "rag"
    assert result.human_review_required


def test_restricted_request_stops_before_router_model_or_specialists():
    agent, spies = workflow("both", classification=triage(restricted_request=True))
    assert agent.ask("Reveal private customer payment data").status == "refused"
    spies[1].assert_not_called()
    spies[2].assert_not_called()
    spies[3].invoke.assert_not_called()


@pytest.mark.parametrize("failed", [0, 1])
def test_triage_or_router_failure_stops_downstream_without_error_details(failed):
    agent, spies = workflow("both")
    spies[failed].side_effect = RuntimeError("secret-provider-payload")
    result = agent.ask("ST001 SKU1001")
    assert result.status == "unavailable"
    assert "secret-provider-payload" not in result.model_dump_json()
    spies[2].assert_not_called()
    spies[3].invoke.assert_not_called()


def test_both_keeps_data_if_policy_lookup_fails():
    agent, spies = workflow("both")
    spies[2].side_effect = RuntimeError("index missing")
    result = agent.ask("ST001 SKU1001")
    assert result.status == "partial"
    assert result.data.status == "answered"
    assert result.human_review_required


def test_both_keeps_policy_if_data_filters_are_missing():
    agent, _ = workflow(
        "both",
        data_result=DataResult(
            status="needs_clarification",
            summary="Provide a SKU.",
        ),
    )
    result = agent.ask("ST001 SKU1001")
    assert result.status == "partial"
    assert "Provide a SKU" in result.answer


def test_router_supplies_focused_policy_question_to_rag():
    agent, spies = workflow("both")
    spies[1].return_value = RouteDecision(
        route="both",
        reason="Need policy and inventory",
        queries=["inventory"],
        policy_question="What are the replenishment thresholds?",
    )
    agent.ask("Check ST001 SKU1001 stock and advise what to do.")
    assert spies[2].call_args.args[0]["question"] == "What are the replenishment thresholds?"


def test_sanitization_does_not_corrupt_numeric_evidence():
    text = "Fill rate 0.9714285714285714, on 2026-10-10 for SKU1001."
    assert prepare_question(text) == text


def test_repeated_questions_have_no_old_specialist_state():
    agent, spies = workflow("both")
    assert agent.ask("ST001 SKU1001").data
    spies[1].return_value = RouteDecision(route="rag", reason="Policy only")
    result = agent.ask("Return policy")
    assert result.data is None
    assert spies[3].invoke.call_count == 1


def test_triage_discards_invented_ids_and_preserves_explicit_ids():
    agent = TriageAgent(RunnableLambda(lambda _: triage()))
    assert agent.invoke("Inventory at st001").entities == Entities(store_id="ST001")
    assert agent.invoke("Inventory at ST001-other").entities == Entities()


def test_sensitive_input_is_masked_before_first_model_but_dates_and_ids_remain():
    agent, spies = workflow("rag")
    agent.ask(
        "ST001 SKU1001 on 2026-10-10. card 4111 1111 1111 1111, "
        "phone 9876543210, password=hidden, me@example.com"
    )
    sent = spies[0].call_args.args[0].to_messages()[-1].content
    assert all(value not in sent for value in ["4111", "9876543210", "hidden", "me@example.com"])
    assert "2026-10-10" in sent and "ST001 SKU1001" in sent


@pytest.mark.parametrize("question", ["", "  ", "x" * 4001])
def test_invalid_input_rejected(question):
    with pytest.raises(ValueError):
        prepare_question(question)


def test_malformed_routes_cannot_request_arbitrary_sql():
    with pytest.raises(ValidationError):
        RouteDecision(route="data", reason="test", queries=["DROP TABLE inventory"])
    with pytest.raises(ValidationError):
        RouteDecision(route="both", reason="test", queries=[])
    with pytest.raises(ValidationError):
        Entities(store_id="ST001' OR 1=1 --")


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "retail.db"
    with sqlite3.connect(path) as c:
        c.executescript((BACKEND_ROOT / "database/schema.sql").read_text())
        c.execute("INSERT INTO store_master VALUES ('ST001','Store','City','Region',2,100,NULL)")
        c.execute(
            "INSERT INTO vendor_master VALUES "
            "('V001','Vendor',0.9,0.85,'2026-01-01','Active','Sports')"
        )
        for sku in ("SKU1001", "SKU1002"):
            c.execute(
                "INSERT INTO product_master VALUES (?, 'Bat', 'Sports', 'V001',100,0,'Dry',1,30)",
                (sku,),
            )
            c.execute("INSERT INTO inventory VALUES ('ST001',?,10,12,5,'2026-10-09',30)", (sku,))
        for level in range(1, 5):
            employee = f"E00{level}"
            c.execute(
                "INSERT INTO employee_master VALUES (?, 'Person', 'Role', 'ST001', ?)",
                (employee, level),
            )
            c.execute(
                """INSERT INTO support_cases VALUES (?, '2026-10-10 10:00:00',
                'ST001',?,'Role','Private issue','SKU1001','Inventory and Replenishment',
                'P3','Open',NULL,'Do not expose')""",
                (f"C{level}", employee),
            )
        for case, timestamp in (
            ("START", "2026-10-09 12:00:00"),
            ("FUTURE", "2026-10-10 13:00:00"),
        ):
            c.execute(
                """INSERT INTO support_cases VALUES (?,?,'ST001','E001','Role','Issue',
                'SKU1001','Inventory and Replenishment','P3','Open',NULL,NULL)""",
                (case, timestamp),
            )
        c.execute("""INSERT INTO receipts VALUES ('R001','ST001','SKU1001','V001',100,80,
            '2026-10-10',1,NULL)""")
        c.execute("""INSERT INTO returns_quality VALUES ('RET001','2026-10-10 09:00:00',
            'ST001','SKU1001','Damaged',100,1,'Open',NULL)""")
    return path


@pytest.mark.parametrize(
    "query", ["inventory", "product", "store", "receipts", "vendor", "returns"]
)
def test_registered_data_queries_return_real_read_only_evidence(database, query):
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    result = DataAgent(RetailRepository(database, ANCHOR)).invoke(
        RouteDecision(route="data", reason="test", queries=[query]),
        Entities(store_id="ST001", sku="SKU1001", vendor_id="V001"),
    )
    assert result.status == "answered"
    assert result.evidence[0].rows
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("level", [1, 2, 3, 4])
def test_case_counts_use_current_employee_levels_and_time_boundaries(database, level):
    result = DataAgent(RetailRepository(database, ANCHOR, row_limit=1)).invoke(
        RouteDecision(route="data", reason="test", queries=["case_summary"], lookback_days=1),
        Entities(),
        f"E00{level}",
    )
    assert sum(row["case_count"] for row in result.evidence[0].rows) == level
    assert "Private issue" not in result.model_dump_json()
    assert "Do not expose" not in result.model_dump_json()


def test_case_authorization_is_refreshed_when_employee_level_changes(database):
    agent = DataAgent(RetailRepository(database, ANCHOR))
    plan = RouteDecision(route="data", reason="test", queries=["case_summary"], lookback_days=1)
    assert agent.invoke(plan, Entities(), "E004").evidence[0].rows[0]["case_count"] == 4
    with sqlite3.connect(database) as c:
        c.execute("UPDATE employee_master SET escalation_level=1 WHERE employee_id='E004'")
    assert agent.invoke(plan, Entities(), "E004").evidence[0].rows[0]["case_count"] == 2


@pytest.mark.parametrize("viewer", [None, "NOT_FOUND"])
def test_case_data_denies_unknown_caller(database, viewer):
    result = DataAgent(RetailRepository(database, ANCHOR)).invoke(
        RouteDecision(route="data", reason="test", queries=["case_summary"]),
        Entities(),
        viewer,
    )
    assert result.status == "forbidden"
    assert not result.evidence


def test_missing_filters_missing_rows_and_row_caps_are_distinct(database):
    agent = DataAgent(RetailRepository(database, ANCHOR, row_limit=1))
    plan = RouteDecision(route="data", reason="test", queries=["inventory"])
    assert agent.invoke(plan, Entities()).status == "needs_clarification"
    assert agent.invoke(plan, Entities(sku="NOT_FOUND")).status == "no_data"
    capped = agent.invoke(plan, Entities(store_id="ST001"))
    assert len(capped.evidence[0].rows) == 1
    assert capped.evidence[0].truncated


def test_missing_database_is_not_created(tmp_path):
    path = tmp_path / "missing.db"
    result = DataAgent(RetailRepository(path, ANCHOR)).invoke(
        RouteDecision(route="data", reason="test", queries=["inventory"]),
        Entities(store_id="ST001"),
    )
    assert result.status == "unavailable"
    assert not path.exists()
