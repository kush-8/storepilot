"""Actual HTTP/repository behaviour across every viewer/creator combination."""

import json
import sqlite3
from itertools import product

import pytest

from tests.support import EMPLOYEES, expect


@pytest.mark.parametrize("viewer,creator", list(product(range(1, 5), repeat=2)))
def test_direct_ticket_read_obeys_current_levels(client, auth, viewer, creator):
    response = client.get(f"/api/tickets/SP-L{creator}-OPEN", headers=auth(viewer))
    if creator <= viewer:
        assert expect(response, 200, "TicketDetail")["created_by_employee_id"] == EMPLOYEES[creator]
    else:
        expect(response, 404, "Error")
        assert f"L{creator}_OPEN_SENTINEL" not in response.text


@pytest.mark.parametrize("viewer", range(1, 5))
def test_list_totals_and_pagination_include_only_visible_creators(client, auth, viewer):
    headers = auth(viewer)
    body = expect(
        client.get("/api/tickets", params={"window": "all"}, headers=headers), 200, "TicketList"
    )
    expected = {
        f"SP-L{level}-{state}" for level in range(1, viewer + 1) for state in ("OPEN", "CLOSED")
    }
    assert body["total"] == len(expected)
    assert {item["ticket_id"] for item in body["items"]} == expected
    paged = expect(
        client.get("/api/tickets", params={"window": "all", "limit": 1}, headers=headers),
        200,
        "TicketList",
    )
    assert paged["total"] == len(expected) and len(paged["items"]) == 1
    assert paged["context"]["scope"]["viewer_current_level"] == viewer


@pytest.mark.parametrize("viewer", range(1, 5))
def test_dashboard_aggregates_match_authorized_rows(client, auth, viewer):
    body = expect(
        client.get("/api/dashboard", params={"window": "all"}, headers=auth(viewer)),
        200,
        "Dashboard",
    )
    metrics = body["metrics"]
    assert metrics == {
        "total": viewer * 2,
        "open": viewer,
        "in_progress": 0,
        "closed": viewer,
        "unresolved": viewer,
        "p1_unresolved": 0,
        "p2_unresolved": viewer,
    }
    for name in ("by_priority", "by_category", "by_store"):
        assert sum(bucket["count"] for bucket in body[name]) == metrics["total"]


def test_search_and_store_filter_cannot_widen_visibility(client, auth):
    headers = auth(1)
    for parameters in ({"search": "L4_OPEN_SENTINEL"}, {"store_id": "ST004"}):
        body = expect(
            client.get("/api/tickets", params={"window": "all", **parameters}, headers=headers),
            200,
            "TicketList",
        )
        assert body["total"] == 0 and body["items"] == []


def test_hidden_ticket_and_missing_ticket_have_same_safe_error(client, auth):
    headers = auth(1)
    hidden = expect(client.get("/api/tickets/SP-L4-OPEN", headers=headers), 404, "Error")
    missing = expect(client.get("/api/tickets/SP-NONEXISTENT", headers=headers), 404, "Error")
    assert (hidden["code"], hidden["message"]) == (missing["code"], missing["message"])


def test_creator_level_change_is_applied_without_reissuing_viewer_token(client, auth, databases):
    headers = auth(1)
    expect(client.get("/api/tickets/SP-L4-OPEN", headers=headers), 404, "Error")
    with sqlite3.connect(databases["retail"]) as connection:
        connection.execute(
            "UPDATE employee_master SET escalation_level=1 WHERE employee_id='E9004'"
        )
    expect(client.get("/api/tickets/SP-L4-OPEN", headers=headers), 200, "TicketDetail")


def test_viewer_demotion_invalidates_cached_rows_counts_and_detail(client, auth, databases):
    headers = auth(4)
    first = expect(
        client.get("/api/dashboard", params={"window": "all"}, headers=headers), 200, "Dashboard"
    )
    assert first["metrics"]["total"] == 8
    with sqlite3.connect(databases["retail"]) as connection:
        connection.execute(
            "UPDATE employee_master SET escalation_level=1 WHERE employee_id='E9004'"
        )
    second = expect(
        client.get("/api/dashboard", params={"window": "all"}, headers=headers), 200, "Dashboard"
    )
    # Current E9004's own two tickets also become level 1.
    assert second["metrics"]["total"] == 4
    expect(client.get("/api/tickets/SP-L3-OPEN", headers=headers), 404, "Error")


def test_private_chat_is_not_exposed_to_higher_level_employee(client, auth, conversation):
    identifier = conversation(1)
    expect(client.get(f"/api/conversations/{identifier}", headers=auth(1)), 200, "Conversation")
    expect(client.get(f"/api/conversations/{identifier}", headers=auth(4)), 404, "Error")


def test_missing_creator_directory_entry_fails_closed(client, auth, databases):
    with sqlite3.connect(databases["application"]) as connection:
        connection.execute(
            "UPDATE tickets SET created_by_employee_id='E9999' WHERE ticket_id='SP-L1-OPEN'"
        )
    expect(client.get("/api/tickets/SP-L1-OPEN", headers=auth(4)), 404, "Error")


def test_stored_related_evidence_is_rechecked_for_current_viewer(client, auth, databases):
    with sqlite3.connect(databases["application"]) as connection:
        connection.execute(
            "INSERT INTO ticket_evidence VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "related-hidden",
                "SP-L1-OPEN",
                "tickets",
                "SP-L4-OPEN",
                "related_tickets",
                json.dumps({"text": "L4_OPEN_SENTINEL"}),
                None,
                "2026-10-10T06:00:00Z",
            ),
        )
    response = client.get("/api/tickets/SP-L1-OPEN", headers=auth(1))
    expect(response, 200, "TicketDetail")
    assert "L4_OPEN_SENTINEL" not in response.text
    assert "SP-L4-OPEN" not in response.text
