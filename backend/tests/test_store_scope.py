"""Reporting is restricted to the employee's current assigned store."""

from uuid import uuid4

import pytest

from app.storage import get_record, put_record, state
from tests.support import expect


def send(client, headers, conversation, **changes):
    body = dict(
        content="One register card reader is down since 10am, error E42. Other registers work.",
        client_message_id=str(uuid4()),
    )
    body.update(changes)
    return client.post(f"/api/conversations/{conversation}/messages", headers=headers, json=body)


@pytest.mark.parametrize("level", [1, 2, 3, 4])
def test_all_levels_cannot_create_conversations_for_another_store(client, auth, level):
    expect(
        client.post("/api/conversations", headers=auth(level), json={"affected_store_id": "ST005"}),
        403,
        "Error",
    )


def test_warehouse_cannot_bypass_assigned_store_reporting(client, auth):
    expect(
        client.post("/api/conversations", headers=auth(), json={"affected_store_id": "WH001"}),
        403,
        "Error",
    )


def test_message_context_cannot_switch_store(client, auth):
    headers = auth()
    conversation = expect(
        client.post("/api/conversations", headers=headers, json={}), 201, "Conversation"
    )["conversation_id"]
    expect(
        send(client, headers, conversation, context={"affected_store_id": "ST002"}), 403, "Error"
    )
    history = expect(
        client.get(f"/api/conversations/{conversation}", headers=headers), 200, "Conversation"
    )
    assert history["affected_store_id"] == "ST001" and history["messages"] == []


def test_legacy_conversation_for_another_store_cannot_report_new_issues(client, auth):
    headers = auth()
    conversation = expect(
        client.post("/api/conversations", headers=headers, json={}), 201, "Conversation"
    )["conversation_id"]
    with state() as db:
        record = get_record(db, "conversation", conversation)
        record["affected_store_id"] = "ST002"
        put_record(db, "conversation", conversation, record["owner_employee_id"], record)
    expect(send(client, headers, conversation), 403, "Error")


def test_draft_store_is_checked_again_at_commit(client, auth):
    headers = auth()
    conversation = expect(
        client.post("/api/conversations", headers=headers, json={}), 201, "Conversation"
    )["conversation_id"]
    draft = expect(send(client, headers, conversation), 200, "ChatTurn")["ticket_draft"]
    with state() as db:
        record = get_record(db, "draft", draft["draft_id"])
        owner = db.execute(
            "SELECT owner FROM records WHERE kind='draft' AND id=?", (draft["draft_id"],)
        ).fetchone()[0]
        record["affected_store_id"] = "ST002"
        put_record(db, "draft", draft["draft_id"], owner, record)
    expect(
        client.post(
            "/api/tickets",
            headers={**headers, "Idempotency-Key": "foreign-store-save"},
            json={"draft_id": draft["draft_id"], "draft_revision": draft["revision"]},
        ),
        403,
        "Error",
    )
    with state() as db:
        assert db.execute("SELECT COUNT(*) FROM records WHERE kind='ticket'").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] == 0


def test_foreign_store_in_text_requires_clarification_and_followup_can_recover(client, auth):
    headers = auth()
    conversation = expect(
        client.post("/api/conversations", headers=headers, json={}), 201, "Conversation"
    )["conversation_id"]
    response = expect(
        send(
            client,
            headers,
            conversation,
            content="One register at ST002 is down since 10am, error E42.",
        ),
        200,
        "ChatTurn",
    )
    assert response["result_type"] == "clarification"
    assert response["ticket_draft"] is None
    assert "ST001" in response["follow_up_question"]
    corrected = expect(send(client, headers, conversation), 200, "ChatTurn")
    assert corrected["ticket_draft"]["affected_store_id"] == "ST001"
    assert "ST002" not in corrected["ticket_draft"]["description"]


@pytest.mark.parametrize("level", [1, 2, 3, 4])
def test_own_store_is_derived_from_current_directory_for_conversation_draft_and_ticket(
    client, auth, level
):
    headers = auth(level)
    store = f"ST00{level}"
    conversation = expect(
        client.post("/api/conversations", headers=headers, json={}), 201, "Conversation"
    )
    assert conversation["affected_store_id"] == store
    draft = expect(send(client, headers, conversation["conversation_id"]), 200, "ChatTurn")[
        "ticket_draft"
    ]
    assert draft["affected_store_id"] == store
    created = expect(
        client.post(
            "/api/tickets",
            headers={**headers, "Idempotency-Key": str(uuid4())},
            json={"draft_id": draft["draft_id"], "draft_revision": draft["revision"]},
        ),
        201,
        "TicketCreated",
    )
    assert created["ticket"]["affected_store_id"] == store
