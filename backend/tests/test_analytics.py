"""Dashboard analytics, source/time modes and scope before aggregation."""

import json
import sqlite3
from datetime import timedelta

import pytest

from tests.support import EMPLOYEES, expect, iso, utc_now


@pytest.mark.parametrize("viewer", range(1, 5))
def test_analytics_uses_authorized_full_dataset_not_page_size(client, auth, model, viewer):
    model.set_response("route", intent="analytics", route="Data", query_template_id="ticket_counts")
    model.set_response(
        "compose",
        answer="Visible unresolved tickets are summarized by store.",
        recommendations=[],
        citations=[],
    )
    body = expect(
        client.post(
            "/api/dashboard/analytics",
            headers=auth(viewer),
            json={
                "question": "Count unresolved tickets by store.",
                "filters": {"window": "all", "status": "Open"},
            },
        ),
        200,
        "AnalyticsResponse",
    )
    assert body["result_type"] == "answer" and body["query_template_ids"]
    assert sum(row["ticket_count"] for row in body["rows"]) == viewer
    assert body["context"]["scope"]["viewer_current_level"] == viewer
    for hidden in range(viewer + 1, 5):
        assert f"L{hidden}_OPEN_SENTINEL" not in json.dumps(body)
        assert f"L{hidden}_OPEN_SENTINEL" not in json.dumps(model.calls)


def test_hidden_ticket_cannot_leak_via_a_direct_analytics_question(client, auth, model):
    model.set_response(
        "route", intent="analytics", route="Data", query_template_id="related_tickets"
    )
    response = client.post(
        "/api/dashboard/analytics",
        headers=auth(1),
        json={"question": "Describe ticket SP-L4-OPEN.", "filters": {"window": "all"}},
    )
    body = expect(response, 200, "AnalyticsResponse")
    assert "L4_OPEN_SENTINEL" not in response.text
    assert "Level 4 open report" not in response.text
    assert "L4_OPEN_SENTINEL" not in json.dumps(model.calls)
    assert body["result_type"] in {"answer", "clarification", "unsupported"}


def test_live_window_includes_new_tickets_after_the_challenge_anchor(client, auth, databases):
    end = utc_now().replace(microsecond=0)
    start = end - timedelta(hours=1)
    with sqlite3.connect(databases["application"]) as connection:
        connection.execute(
            "UPDATE tickets SET created_at_utc=? WHERE ticket_id='SP-L1-OPEN'",
            (iso(end - timedelta(minutes=1)),),
        )
    body = expect(
        client.get(
            "/api/tickets",
            headers=auth(1),
            params={"data_mode": "live", "start": iso(start), "end": iso(end)},
        ),
        200,
        "TicketList",
    )
    assert "SP-L1-OPEN" in {item["ticket_id"] for item in body["items"]}


def test_rolling_window_excludes_start_includes_end_and_excludes_future(client, auth, databases):
    end = utc_now().replace(microsecond=0)
    start = end - timedelta(hours=24)
    times = {1: start, 2: start + timedelta(seconds=1), 3: end, 4: end + timedelta(seconds=1)}
    with sqlite3.connect(databases["application"]) as connection:
        for level, moment in times.items():
            connection.execute(
                "UPDATE tickets SET created_at_utc=? WHERE created_by_employee_id=?",
                (iso(moment), EMPLOYEES[level]),
            )
    body = expect(
        client.get("/api/tickets", headers=auth(4), params={"start": iso(start), "end": iso(end)}),
        200,
        "TicketList",
    )
    assert {item["created_by_employee_id"] for item in body["items"]} == {"E9002", "E9003"}
    assert body["total"] == 4


@pytest.mark.parametrize(
    "parameters",
    [
        {"start": "2026-10-10T00:00:00Z"},
        {"start": "2026-10-11T00:00:00Z", "end": "2026-10-10T00:00:00Z"},
        {"window": "last24h", "start": "2026-10-09T00:00:00Z", "end": "2026-10-10T00:00:00Z"},
        {
            "data_mode": "historical_snapshot",
            "start": "2026-10-09T00:00:00Z",
            "end": "2026-10-11T00:00:00Z",
        },
    ],
)
def test_invalid_or_mixed_time_filters_are_rejected(client, auth, parameters):
    expect(client.get("/api/tickets", headers=auth(1), params=parameters), 422, "Error")


def test_sql_injection_is_bound_as_search_data_not_executed(client, auth, databases):
    body = expect(
        client.get(
            "/api/tickets",
            headers=auth(4),
            params={"window": "all", "search": "'; DROP TABLE tickets; --"},
        ),
        200,
        "TicketList",
    )
    assert body["items"] == []
    with sqlite3.connect(databases["application"]) as connection:
        assert connection.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 8


def test_analytics_follow_up_thread_is_owner_only(client, auth, model):
    model.set_response("route", intent="analytics", route="Data", query_template_id="ticket_counts")
    body = expect(
        client.post(
            "/api/dashboard/analytics",
            headers=auth(1),
            json={"question": "Count my visible tickets."},
        ),
        200,
        "AnalyticsResponse",
    )
    expect(
        client.post(
            "/api/dashboard/analytics",
            headers=auth(4),
            json={
                "question": "Continue that analysis.",
                "analytics_thread_id": body["analytics_thread_id"],
            },
        ),
        404,
        "Error",
    )
