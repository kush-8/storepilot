"""Persisted status transitions and atomic lifecycle events; no operational approvals."""

import sqlite3

import pytest

from tests.support import expect


@pytest.mark.parametrize(
    "initial,next_status,reason",
    [
        ("Open", "In Progress", None),
        ("Open", "Closed", None),
        ("In Progress", "Open", None),
        ("In Progress", "Closed", None),
        ("Closed", "Open", "The issue recurred."),
    ],
)
def test_creator_transition_records_event_and_version(
    client, auth, databases, initial, next_status, reason
):
    with sqlite3.connect(databases["application"]) as connection:
        connection.execute("UPDATE tickets SET status=? WHERE ticket_id='SP-L1-OPEN'", (initial,))
    payload = {"status": next_status, "expected_version": 1}
    if reason:
        payload["reason"] = reason
    body = expect(
        client.patch("/api/tickets/SP-L1-OPEN/status", headers=auth(1), json=payload),
        200,
        "TicketDetail",
    )
    assert body["status"] == next_status and body["version"] == 2
    assert bool(body["closed_at"]) == (next_status == "Closed")
    with sqlite3.connect(databases["application"]) as connection:
        rows = connection.execute(
            "SELECT actor_employee_id, old_status, new_status, ticket_version "
            "FROM ticket_events WHERE ticket_id='SP-L1-OPEN' AND event_type='status_changed'"
        ).fetchall()
    assert rows == [("E9001", initial, next_status, 2)]


def test_visibility_does_not_grant_mutation(client, auth):
    expect(client.get("/api/tickets/SP-L1-OPEN", headers=auth(4)), 200, "TicketDetail")
    expect(
        client.patch(
            "/api/tickets/SP-L1-OPEN/status",
            headers=auth(4),
            json={"status": "Closed", "expected_version": 1},
        ),
        403,
        "Error",
    )


def test_hidden_mutation_does_not_reveal_ticket_exists(client, auth):
    expect(
        client.patch(
            "/api/tickets/SP-L4-OPEN/status",
            headers=auth(1),
            json={"status": "Closed", "expected_version": 1},
        ),
        404,
        "Error",
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "Open", "expected_version": 1},
        {"status": "Closed", "expected_version": 99},
    ],
)
def test_invalid_transition_or_stale_version_does_not_write_event(client, auth, databases, payload):
    expect(
        client.patch("/api/tickets/SP-L1-OPEN/status", headers=auth(1), json=payload), 409, "Error"
    )
    with sqlite3.connect(databases["application"]) as connection:
        assert connection.execute("SELECT COUNT(*) FROM ticket_events").fetchone()[0] == 0
        assert connection.execute(
            "SELECT status,version FROM tickets WHERE ticket_id='SP-L1-OPEN'"
        ).fetchone() == ("Open", 1)


def test_reopen_requires_a_reason(client, auth):
    expect(
        client.patch(
            "/api/tickets/SP-L1-CLOSED/status",
            headers=auth(1),
            json={"status": "Open", "expected_version": 1},
        ),
        422,
        "Error",
    )
