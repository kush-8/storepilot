"""Real endpoints for clarification, private chat and durable ticket creation."""

import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from tests.support import expect


def create_draft(client, headers):
    conversation = expect(
        client.post("/api/conversations", headers=headers, json={"affected_store_id": "ST003"}),
        201,
        "Conversation",
    )
    response = client.post(
        f"/api/conversations/{conversation['conversation_id']}/messages",
        headers=headers,
        json={
            "content": "One reader on REG-01 at ST003 is failing; other registers work.",
            "client_message_id": str(uuid4()),
            "context": {"affected_store_id": "ST003"},
        },
    )
    body = expect(response, 200, "ChatTurn")
    draft = body["ticket_draft"]
    assert draft is not None and draft["generation_allowed"]
    return draft, conversation["conversation_id"]


def generate(client, headers, draft, key="test-idempotency-key"):
    return client.post(
        "/api/tickets",
        headers={**headers, "Idempotency-Key": key},
        json={"draft_id": draft["draft_id"], "draft_revision": draft["revision"]},
    )


def test_recommended_steps_can_be_saved_as_a_structured_ticket(client, auth, databases):
    headers = auth(1)
    draft, identifier = create_draft(client, headers)
    body = expect(generate(client, headers, draft), 201, "TicketCreated")
    ticket = body["ticket"]
    assert ticket["created_by_employee_id"] == "E9001"
    assert ticket["priority"] == "P3" and ticket["status"] == "Open"
    assert ticket["recommendations"] and ticket["citations"]
    detail = expect(
        client.get(f"/api/tickets/{ticket['ticket_id']}", headers=headers), 200, "TicketDetail"
    )
    assert detail["recommendations"] == ticket["recommendations"]
    with sqlite3.connect(databases["application"]) as connection:
        assert connection.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 9
        assert (
            connection.execute(
                "SELECT conversation_id FROM tickets WHERE ticket_id=?", (ticket["ticket_id"],)
            ).fetchone()[0]
            == identifier
        )
        for table in ("ticket_steps", "ticket_citations", "ticket_events"):
            assert (
                connection.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE ticket_id=?", (ticket["ticket_id"],)
                ).fetchone()[0]
                > 0
            )


def test_draft_read_is_owner_only_and_matches_chat_revision(client, auth):
    draft, _ = create_draft(client, auth(1))
    path = f"/api/ticket-drafts/{draft['draft_id']}"
    saved = expect(client.get(path, headers=auth(1)), 200, "Draft")
    assert saved == draft
    expect(client.get(path, headers=auth(4)), 404, "Error")


def test_same_key_retries_return_same_ticket_and_do_not_duplicate_children(client, auth, databases):
    headers = auth(1)
    draft, _ = create_draft(client, headers)
    first = expect(generate(client, headers, draft), 201, "TicketCreated")
    second = expect(generate(client, headers, draft), 200, "TicketCreated")
    assert second["idempotent_replay"] is True
    assert first["ticket"]["ticket_id"] == second["ticket"]["ticket_id"]
    with sqlite3.connect(databases["application"]) as connection:
        assert connection.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 9
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM ticket_events WHERE ticket_id=? AND event_type='created'",
                (first["ticket"]["ticket_id"],),
            ).fetchone()[0]
            == 1
        )


def test_reused_key_with_different_draft_conflicts(client, auth):
    headers = auth(1)
    draft, _ = create_draft(client, headers)
    expect(generate(client, headers, draft), 201, "TicketCreated")
    changed = {**draft, "revision": draft["revision"] + 1}
    expect(generate(client, headers, changed), 409, "Error")


def test_another_key_cannot_generate_same_draft_twice(client, auth, databases):
    headers = auth(1)
    draft, _ = create_draft(client, headers)
    expect(generate(client, headers, draft, "first-save-key"), 201, "TicketCreated")
    expect(generate(client, headers, draft, "second-save-key"), 409, "Error")
    with sqlite3.connect(databases["application"]) as connection:
        assert connection.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 9


def test_simultaneous_retries_have_one_committed_ticket(client, auth, databases):
    headers = auth(1)
    draft, _ = create_draft(client, headers)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: generate(client, headers, draft), range(2)))
    assert sorted(r.status_code for r in responses) == [200, 201]
    assert len({r.json()["ticket"]["ticket_id"] for r in responses}) == 1
    with sqlite3.connect(databases["application"]) as connection:
        assert connection.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 9


def test_failed_event_insert_rolls_back_the_whole_ticket(client, auth, databases):
    headers = auth(1)
    draft, _ = create_draft(client, headers)
    with sqlite3.connect(databases["application"]) as connection:
        connection.executescript(
            "CREATE TRIGGER fail_creation_event BEFORE INSERT ON ticket_events "
            "WHEN NEW.event_type='created' BEGIN SELECT RAISE(ABORT,'test write failure'); END;"
        )
    expect(generate(client, headers, draft), 503, "Error")
    with sqlite3.connect(databases["application"]) as connection:
        assert connection.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 8
        for table in (
            "ticket_steps",
            "ticket_citations",
            "ticket_evidence",
            "ticket_events",
            "idempotency_receipts",
        ):
            assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_expired_or_other_employee_draft_cannot_be_generated(client, auth, databases):
    headers = auth(1)
    draft, _ = create_draft(client, headers)
    expect(generate(client, auth(4), draft), 404, "Error")
    with sqlite3.connect(databases["application"]) as connection:
        connection.execute("UPDATE ticket_drafts SET expires_at_utc='2000-01-01T00:00:00Z'")
    expect(generate(client, headers, draft), 409, "Error")


def test_client_priority_and_creator_overrides_are_rejected(client, auth):
    headers = auth(1)
    draft, _ = create_draft(client, headers)
    expect(
        client.post(
            "/api/tickets",
            headers={**headers, "Idempotency-Key": "spoofing-test-key"},
            json={
                "draft_id": draft["draft_id"],
                "draft_revision": draft["revision"],
                "created_by_employee_id": "E9004",
                "priority": "P4",
            },
        ),
        422,
        "Error",
    )


def test_sensitive_message_is_sanitized_before_model_storage_and_response(
    client, auth, model, databases, caplog
):
    headers = auth(1)
    conversation = expect(
        client.post("/api/conversations", json={}, headers=headers), 201, "Conversation"
    )
    phone = "9876543210"
    card = "4111 1111 1111 1111"
    response = client.post(
        f"/api/conversations/{conversation['conversation_id']}/messages",
        headers=headers,
        json={
            "client_message_id": str(uuid4()),
            "content": f"Phone {phone}; card {card}; one card reader is failing.",
        },
    )
    body = expect(response, 200, "ChatTurn")
    assert body["guardrails"]["pii_checked"] and body["guardrails"]["pii_detected"]
    with sqlite3.connect(databases["application"]) as connection:
        stored = str(
            connection.execute("SELECT sanitized_content FROM conversation_messages").fetchall()
        )
    for value in (phone, card, card.replace(" ", "")):
        assert value not in response.text
        assert value not in json.dumps(model.calls)
        assert value not in stored and value not in caplog.text


def test_message_retry_is_one_logical_turn(client, auth, conversation, databases):
    identifier = conversation(1)
    headers = auth(1)
    payload = {
        "content": "One register's card reader is failing; other registers work.",
        "client_message_id": str(uuid4()),
    }
    path = f"/api/conversations/{identifier}/messages"
    first = expect(client.post(path, json=payload, headers=headers), 200, "ChatTurn")
    second = expect(client.post(path, json=payload, headers=headers), 200, "ChatTurn")
    assert first["assistant_message"]["message_id"] == second["assistant_message"]["message_id"]
    expect(
        client.post(path, json={**payload, "content": "Different issue"}, headers=headers),
        409,
        "Error",
    )
    with sqlite3.connect(databases["application"]) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM conversation_messages "
                "WHERE conversation_id=? AND role='user'",
                (identifier,),
            ).fetchone()[0]
            == 1
        )


def test_ticket_save_does_not_modify_the_retail_snapshot(client, auth, databases):
    before = hashlib.sha256(databases["retail"].read_bytes()).hexdigest()
    headers = auth(1)
    draft, _ = create_draft(client, headers)
    expect(generate(client, headers, draft), 201, "TicketCreated")
    assert hashlib.sha256(databases["retail"].read_bytes()).hexdigest() == before
