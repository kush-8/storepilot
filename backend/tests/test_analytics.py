"""Natural-language analytics: real SQL execution, scope and evidence, offline planning."""

import hashlib
import json
import sqlite3
from datetime import datetime
from unittest.mock import Mock

import pytest
from langchain_core.runnables import RunnableLambda

from app.agents.data.agent import DataAgent
from app.agents.data.sql_tool import ReadOnlySqlExecutor
from tests.support import BACKEND, assert_schema

ANCHOR = datetime.fromisoformat("2026-10-10T12:00:00+05:30")


def agent_for(sql, database=BACKEND / "database/retail.db", **plan):
    planner = Mock(return_value={"intent": "retail_query", "sql": sql, **plan})
    agent = DataAgent(
        RunnableLambda(lambda _: {}),
        ReadOnlySqlExecutor(database),
        ANCHOR,
        analytics_model=RunnableLambda(planner),
    )
    return agent, planner


def test_frequent_issue_ranks_only_supplied_tickets_and_respects_question_store():
    agent, planner = agent_for(
        "SELECT category, COUNT(*) AS tickets FROM visible_tickets "
        "WHERE affected_store_id='ST004' GROUP BY category ORDER BY tickets DESC LIMIT 1"
    )
    result = agent.analyze(
        "What is the most frequent issue in store ST004?",
        authorized_tickets=[
            {"affected_store_id": "ST004", "category": "POS and Payments", "status": "Open"},
            {"affected_store_id": "ST004", "category": "POS and Payments", "status": "Open"},
            {"affected_store_id": "ST004", "category": "Customer Service", "status": "Closed"},
            {
                "affected_store_id": "ST002",
                "category": "Other",
                "status": "Open",
                "description": "PRIVATE_SENTINEL",
                "created_by_employee_id": "E9001",
            },
        ],
    )
    assert result.status == "answer"
    assert result.rows == [{"category": "POS and Payments", "tickets": 2}]
    assert result.columns[1]["value_type"] == "number"
    assert "POS and Payments" in result.answer
    assert "PRIVATE_SENTINEL" not in str(planner.call_args)
    assert "E9001" not in str(planner.call_args)


@pytest.mark.parametrize(
    "sql,table",
    [
        (
            "SELECT store_id, sku, on_hand FROM inventory WHERE on_hand<reorder_point "
            "ORDER BY store_id,sku",
            "inventory",
        ),
        (
            "SELECT name, on_time_rate FROM vendor_master ORDER BY on_time_rate LIMIT 3",
            "vendor_master",
        ),
        (
            "SELECT category, ROUND(AVG(list_price),2) AS price "
            "FROM product_master GROUP BY category",
            "product_master",
        ),
        (
            "SELECT store_id, SUM(po_qty-received_qty) AS shortage FROM receipts GROUP BY store_id",
            "receipts",
        ),
        (
            "SELECT reason, COUNT(*) AS returns, SUM(refund_amount_inr) AS refunds "
            "FROM returns_quality GROUP BY reason",
            "returns_quality",
        ),
        (
            "SELECT category, team, sla_minutes FROM escalation_matrix ORDER BY category",
            "escalation_matrix",
        ),
        (
            "SELECT DATE(created_at) AS day, COUNT(*) AS tickets FROM visible_tickets GROUP BY day",
            "visible_tickets",
        ),
    ],
)
def test_analytics_supports_operational_data_and_ticket_trends(sql, table):
    agent, _ = agent_for(sql)
    result = agent.analyze(
        "Analyze the available store data",
        authorized_tickets=[{"created_at": "2026-10-09T10:00:00+05:30", "status": "Open"}],
    )
    assert result.status == "answer" and result.rows
    assert result.query_template_ids == ["validated_retail_analytics"]
    assert table in result.evidence[0]["source"]


def test_operational_filters_cannot_be_removed_by_generated_sql():
    agent, _ = agent_for("SELECT store_id, sku FROM inventory ORDER BY sku")
    result = agent.analyze(
        "List inventory",
        authorized_tickets=[],
        context={
            "filters": {"store_id": "ST004", "sku": "SKU1001"},
            "time_window": {"start": None, "end": ANCHOR.isoformat()},
        },
    )
    assert result.status == "answer" and result.rows
    assert all(row == {"store_id": "ST004", "sku": "SKU1001"} for row in result.rows)


def test_temporal_data_respects_window_even_without_sql_predicate():
    agent, _ = agent_for("SELECT COUNT(*) AS receipts FROM receipts")
    result = agent.analyze(
        "Count deliveries",
        authorized_tickets=[],
        context={
            "filters": {},
            "time_window": {
                "start": "2026-11-01T00:00:00+05:30",
                "end": "2026-11-02T00:00:00+05:30",
            },
        },
    )
    assert result.status == "answer" and result.rows == [{"receipts": 0}]


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM inventory",
        "SELECT * FROM inventory",
        "SELECT employee_id FROM employee_master",
        "SELECT issue_text FROM support_cases",
        "SELECT payload FROM records",
        "SELECT status FROM main.support_cases",
        "SELECT employee_id FROM visible_tickets",
        "SELECT description FROM visible_tickets",
        "SELECT load_extension('file') FROM inventory",
        "SELECT readfile('database/storepilot.db') FROM inventory",
        "SELECT sku FROM inventory; DROP TABLE inventory",
        "SELECT sku FROM inventory -- bypass",
        "SELECT sql FROM sqlite_master",
        "PRAGMA database_list",
        "WITH secret AS (SELECT employee_name FROM employee_master) "
        "SELECT employee_name FROM secret",
    ],
)
def test_generated_analytics_cannot_read_private_data_or_mutate_database(sql):
    path = BACKEND / "database/retail.db"
    before = hashlib.sha256(path.read_bytes()).digest()
    agent, _ = agent_for(sql)
    result = agent.analyze(
        "Analyze store data",
        authorized_tickets=[{"description": "PRIVATE_SENTINEL", "created_by_employee_id": "E9001"}],
    )
    assert result.status in {"refusal", "unavailable"} and not result.rows
    assert "PRIVATE_SENTINEL" not in result.model_dump_json()
    assert hashlib.sha256(path.read_bytes()).digest() == before


def test_result_cap_reports_truncation_and_empty_data_is_explicit():
    agent, _ = agent_for("SELECT store_id, sku FROM inventory ORDER BY store_id,sku")
    result = agent.analyze("List all stock", authorized_tickets=[])
    assert result.status == "answer" and len(result.rows) == 50 and result.truncated
    assert any("50" in value for value in result.limitations)
    agent, _ = agent_for("SELECT category FROM visible_tickets")
    result = agent.analyze("List categories", authorized_tickets=[])
    assert result.status == "answer" and result.rows == []
    assert "No matching" in result.answer


def test_broad_queries_use_real_api_schema_and_current_level_scope(client, auth, databases):
    # The offline planner must recognize broad requests; SQL and authentication stay real.
    response = client.post(
        "/api/dashboard/analytics",
        headers=auth(1),
        json={
            "question": "What is the most frequent issue in store ST004?",
            "filters": {"data_mode": "combined", "window": "all"},
        },
    )
    assert response.status_code == 200
    value = response.json()
    assert_schema(value, "AnalyticsResponse")
    assert value["result_type"] == "answer" and value["intent"] == "retail_query"
    with sqlite3.connect(databases["retail"]) as db:
        expected = db.execute(
            "SELECT c.category_label,COUNT(*) FROM support_cases c JOIN employee_master e "
            "ON e.employee_id=c.employee_id WHERE e.escalation_level<=1 AND c.store_id='ST004' "
            "AND c.created_ts<=? GROUP BY c.category_label ORDER BY COUNT(*) DESC,"
            "c.category_label LIMIT 1",
            (ANCHOR.strftime("%Y-%m-%d %H:%M:%S"),),
        ).fetchone()
    assert value["rows"] == (
        [{"category": expected[0], "tickets": expected[1]}] if expected else []
    )
    response = client.post(
        "/api/dashboard/analytics",
        headers=auth(1),
        json={
            "question": "Which products need replenishment?",
            "filters": {"store_id": "ST004", "data_mode": "combined", "window": "all"},
        },
    )
    value = response.json()
    assert_schema(value, "AnalyticsResponse")
    assert value["result_type"] == "answer" and value["rows"]
    assert all(row["store_id"] == "ST004" for row in value["rows"])
    assert "read-only" in json.dumps(value["limitations"]).lower()


def test_policy_questions_return_grounded_citations_without_ticket_creation(client, auth):
    response = client.post(
        "/api/dashboard/analytics",
        headers=auth(),
        json={
            "question": "Explain the return policy",
            "filters": {"window": "all"},
        },
    )
    value = response.json()
    assert_schema(value, "AnalyticsResponse")
    assert value["intent"] == "policy" and value["result_type"] == "answer"
    assert value["citations"] and value["rows"] == []
    tickets = client.get("/api/tickets?window=all", headers=auth()).json()
    assert tickets["total"] == 0


def test_parameterized_joins_and_cte_queries_are_supported():
    agent, _ = agent_for(
        "WITH stock AS (SELECT store_id,sku,on_hand FROM inventory WHERE store_id=:store) "
        "SELECT s.store_id,p.name,s.on_hand FROM stock s JOIN product_master p "
        "ON p.sku=s.sku ORDER BY p.name LIMIT 5",
        parameters={"store": "ST004"},
    )
    result = agent.analyze("Show five product stock levels for ST004", authorized_tickets=[])
    assert result.status == "answer" and len(result.rows) == 5
    assert all(row["store_id"] == "ST004" for row in result.rows)


def test_expensive_queries_are_bounded():
    agent, _ = agent_for(
        "SELECT COUNT(*) AS total FROM inventory a CROSS JOIN inventory b CROSS JOIN inventory c"
    )
    result = agent.analyze("Analyze inventory", authorized_tickets=[])
    assert result.status == "unavailable" and result.rows == []


def test_explicit_parameter_bindings_survive_structured_model_output():
    agent, _ = agent_for(
        "SELECT COUNT(*) AS tickets FROM visible_tickets WHERE status != :closed",
        parameters=[{"name": "closed", "value": "Closed"}],
    )
    result = agent.analyze(
        "Count unresolved tickets",
        authorized_tickets=[
            {"status": "Open"},
            {"status": "In Progress"},
            {"status": "Closed"},
        ],
    )
    assert result.status == "answer" and result.rows == [{"tickets": 2}]


def test_missing_store_binding_is_grounded_from_question():
    agent, planner = agent_for("SELECT COUNT(*) AS stock FROM inventory WHERE store_id=:store_id")
    result = agent.analyze("How many stock rows in ST004?", authorized_tickets=[])
    assert result.status == "answer" and result.rows[0]["stock"] > 0
    assert planner.call_count == 1


def test_sql_errors_allow_one_correction_without_sending_ticket_rows():
    agent, planner = agent_for("SELECT bad_column FROM visible_tickets")
    planner.side_effect = [
        {"intent": "retail_query", "sql": "SELECT bad_column FROM visible_tickets"},
        {"intent": "retail_query", "sql": "SELECT COUNT(*) AS tickets FROM visible_tickets"},
    ]
    result = agent.analyze(
        "Count tickets", authorized_tickets=[{"status": "Open", "description": "PRIVATE_SENTINEL"}]
    )
    assert result.status == "answer" and result.rows == [{"tickets": 1}]
    assert planner.call_count == 2
    assert "bad_column" in str(planner.call_args) and "PRIVATE_SENTINEL" not in str(
        planner.call_args
    )


def test_ticket_trends_group_by_local_calendar_day():
    agent, _ = agent_for(
        "SELECT DATE(created_at) AS day, COUNT(*) AS tickets FROM visible_tickets GROUP BY day"
    )
    result = agent.analyze(
        "Daily ticket counts",
        authorized_tickets=[
            {"created_at": "2026-10-09T20:00:00+00:00"},
            {"created_at": "2026-10-10T01:00:00+05:30"},
        ],
    )
    assert result.status == "answer" and result.rows == [{"day": "2026-10-10", "tickets": 2}]


@pytest.mark.parametrize(
    "sql,expected",
    [
        (
            "SELECT STRFTIME('%Y-%m',created_at) AS month,COUNT(*) AS tickets "
            "FROM visible_tickets GROUP BY month",
            [{"month": "2026-10", "tickets": 2}],
        ),
        (
            "SELECT ROUND(100.0*SUM(CASE WHEN status='Closed' THEN 1 ELSE 0 END)/COUNT(*),2) "
            "AS closed_percent FROM visible_tickets",
            [{"closed_percent": 50.0}],
        ),
        (
            "SELECT status,DENSE_RANK() OVER (ORDER BY status) AS rank "
            "FROM visible_tickets ORDER BY status",
            [{"status": "Closed", "rank": 1}, {"status": "Open", "rank": 2}],
        ),
    ],
)
def test_monthly_trends_percentages_and_ranking_functions(sql, expected):
    agent, _ = agent_for(sql)
    result = agent.analyze(
        "Analyze ticket trends",
        authorized_tickets=[
            {"created_at": "2026-10-09T10:00:00+05:30", "status": "Open"},
            {"created_at": "2026-10-10T10:00:00+05:30", "status": "Closed"},
        ],
    )
    assert result.status == "answer" and result.rows == expected
