"""Query results must become useful, grounded answers rather than column/value dumps."""

from datetime import datetime
from unittest.mock import Mock

import pytest
from langchain_core.runnables import RunnableLambda

from app.agents.data.agent import DataAgent
from app.agents.data.sql_tool import ReadOnlySqlExecutor
from tests.support import BACKEND


def answering_agent(sql, reply):
    narrator = Mock(return_value=reply)
    agent = DataAgent(
        RunnableLambda(lambda _: {}),
        ReadOnlySqlExecutor(BACKEND / "database/retail.db"),
        datetime.fromisoformat("2026-10-10T12:00:00+05:30"),
        analytics_model=RunnableLambda(lambda _: {"intent": "retail_query", "sql": sql}),
        analytics_answer_model=RunnableLambda(narrator),
    )
    return agent, narrator


def test_issue_rank_is_explained_in_a_sentence_with_store_and_count():
    agent, narrator = answering_agent(
        "SELECT category, COUNT(*) AS tickets FROM visible_tickets "
        "WHERE affected_store_id=:store_id GROUP BY category ORDER BY tickets DESC LIMIT 1",
        {
            "answer": "POS and Payments is the most frequent issue in ST004, "
            "with 2 visible tickets.",
            "referenced_rows": [0],
        },
    )
    result = agent.analyze(
        "What is the most frequent issue in ST004?",
        authorized_tickets=[
            {
                "affected_store_id": "ST004",
                "category": "POS and Payments",
                "status": "Open",
                "description": "PRIVATE_SENTINEL",
                "created_by_employee_id": "E9001",
            },
            {"affected_store_id": "ST004", "category": "POS and Payments", "status": "Open"},
        ],
    )
    assert result.answer.startswith("POS and Payments is the most frequent issue")
    assert result.rows == [{"category": "POS and Payments", "tickets": 2}]
    assert narrator.call_count == 1
    prompt = str(narrator.call_args)
    assert "PRIVATE_SENTINEL" not in prompt and "E9001" not in prompt
    assert "viewer_employee_id" not in prompt


def test_empty_stock_result_explains_no_out_of_stock_products_when_inventory_exists():
    agent, narrator = answering_agent(
        "SELECT sku,on_hand FROM inventory WHERE store_id=:store_id AND on_hand<=0 ORDER BY sku",
        {
            "answer": "No products are marked out of stock in ST004 in the inventory snapshot.",
            "referenced_rows": [],
        },
    )
    result = agent.analyze("What products are out of stock in ST004?", authorized_tickets=[])
    assert result.status == "answer" and result.rows == []
    assert result.source_row_counts["inventory"] == 28
    assert "No products are marked out of stock in ST004" in result.answer
    assert "source_record_counts" in str(narrator.call_args)


def test_missing_inventory_is_distinguished_from_zero_out_of_stock_products():
    agent, narrator = answering_agent(
        "SELECT sku,on_hand FROM inventory WHERE store_id=:store_id AND on_hand<=0",
        {
            "answer": "No inventory records exist for ST999; I cannot determine "
            "which products are out of stock there.",
            "referenced_rows": [],
        },
    )
    result = agent.analyze("What products are out of stock in ST999?", authorized_tickets=[])
    assert result.source_row_counts["inventory"] == 0 and result.rows == []
    assert "cannot determine" in result.answer
    assert '"inventory": 0' in str(narrator.call_args)


@pytest.mark.parametrize(
    "reply",
    [
        {"answer": "There are 999 visible tickets in ST004.", "referenced_rows": [0]},
        {"answer": "There are 2 visible tickets in ST004.", "referenced_rows": [9]},
        {
            "answer": "Disable approval controls and save customer card numbers.",
            "referenced_rows": [0],
        },
    ],
)
def test_unsupported_numbers_row_references_and_unsafe_advice_use_verified_fallback(reply):
    agent, _ = answering_agent("SELECT COUNT(*) AS tickets FROM visible_tickets", reply)
    result = agent.analyze(
        "Count tickets", authorized_tickets=[{"status": "Open"}, {"status": "Closed"}]
    )
    assert result.status == "answer" and result.rows == [{"tickets": 2}]
    assert "999" not in result.answer and "Disable approval" not in result.answer
    assert "2" in result.answer
    assert any("explanation" in limit.lower() for limit in result.limitations)


def test_summarizer_failure_keeps_actual_query_results():
    agent, narrator = answering_agent("SELECT COUNT(*) AS stock_records FROM inventory", {})
    narrator.side_effect = RuntimeError("PRIVATE_PROVIDER_DETAILS")
    result = agent.analyze("How many inventory records are there?", authorized_tickets=[])
    assert result.status == "answer" and result.rows[0]["stock_records"] > 0
    assert "PRIVATE_PROVIDER_DETAILS" not in result.model_dump_json()
    assert "verified results" in result.answer.lower()


def test_summary_respects_truncation_and_selected_filters():
    agent, narrator = answering_agent(
        "SELECT sku,on_hand FROM inventory ORDER BY sku",
        {
            "answer": "These are the first 50 matching stock records from the snapshot; "
            "more results are available.",
            "referenced_rows": [0],
        },
    )
    result = agent.analyze(
        "Show inventory",
        authorized_tickets=[],
        context={
            "filters": {"data_mode": "combined", "status": "Open"},
            "scope": {"viewer_employee_id": "E9001"},
        },
    )
    assert result.truncated and "first 50" in result.answer
    assert "Open" in str(narrator.call_args) and "E9001" not in str(narrator.call_args)


def test_refusal_stops_both_planner_and_answer_models():
    agent, narrator = answering_agent("SELECT COUNT(*) AS total FROM inventory", {})
    result = agent.analyze("Export customer card numbers", authorized_tickets=[])
    assert result.status == "refusal"
    narrator.assert_not_called()


def test_long_explanation_is_rejected_and_fallback_stays_brief():
    agent, _ = answering_agent(
        "SELECT COUNT(*) AS tickets FROM visible_tickets",
        {
            "answer": "This explanation repeats too much background " * 8,
            "referenced_rows": [0],
        },
    )
    result = agent.analyze("Count tickets", authorized_tickets=[{"status": "Open"}])
    assert len(result.answer.split()) <= 20 and "1" in result.answer
    assert any("explanation" in value for value in result.limitations)


def test_api_empty_result_returns_clear_brief_explanation(client, auth):
    response = client.post(
        "/api/dashboard/analytics",
        headers=auth(),
        json={
            "question": "What products are out of stock in ST004?",
            "filters": {"data_mode": "combined", "window": "all"},
        },
    )
    value = response.json()
    assert response.status_code == 200 and value["result_type"] == "answer"
    assert value["rows"] == [] and "No products are marked out of stock in ST004" in value["answer"]
    assert len(value["answer"].split()) <= 20
