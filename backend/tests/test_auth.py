"""Login and JWT behaviour specified by StorePilot's public contract."""

import json
import sqlite3

import pytest

from tests.support import EMPLOYEES, decode_and_check_jwt, expect, utc_now


def test_login_issues_signed_token_for_exact_directory_pair(client, databases):
    before = int(utc_now().timestamp())
    response = client.post("/api/auth/login", json={"employee_id": "E9001", "store_id": "ST001"})
    body = expect(response, 200, "LoginResponse")
    claims = decode_and_check_jwt(body["access_token"])
    assert claims["sub"] == "E9001"
    assert claims["store_id"] == "ST001"
    assert claims["iss"] == "storepilot" and claims["aud"] == "storepilot-api"
    assert before <= claims["iat"] <= int(utc_now().timestamp()) + 1
    assert claims["exp"] - claims["iat"] == 1800
    assert claims["jti"]
    assert body["employee"]["escalation_level"] == 1
    with sqlite3.connect(databases["application"]) as connection:
        stored = str(connection.execute("SELECT * FROM sessions").fetchall())
    assert body["access_token"] not in stored


@pytest.mark.parametrize(
    "pair",
    [
        {"employee_id": "E9001", "store_id": "ST002"},
        {"employee_id": "E9999", "store_id": "ST001"},
        {"employee_id": "E9001", "store_id": "ST999"},
    ],
)
def test_invalid_pairs_do_not_disclose_which_identifier_was_wrong(client, pair):
    body = expect(client.post("/api/auth/login", json=pair), 401, "Error")
    reference = expect(
        client.post("/api/auth/login", json={"employee_id": "E9998", "store_id": "ST998"}),
        401,
        "Error",
    )
    assert (body["code"], body["message"]) == (reference["code"], reference["message"])
    assert pair["employee_id"] not in json.dumps(body)
    assert pair["store_id"] not in json.dumps(body)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"employee_id": "", "store_id": "ST001"},
        {"employee_id": "bad", "store_id": "ST001"},
        {"employee_id": "E9001", "store_id": "../retail.db"},
        {"employee_id": "E9001", "store_id": "ST001", "escalation_level": 4},
    ],
)
def test_login_validates_shape_and_rejects_client_authority(client, payload):
    expect(client.post("/api/auth/login", json=payload), 422, "Error")


@pytest.mark.parametrize(
    "path,method,payload",
    [
        ("/api/me", "get", None),
        ("/api/stores", "get", None),
        ("/api/tickets", "get", None),
        ("/api/dashboard", "get", None),
        ("/api/conversations", "post", {}),
        ("/api/dashboard/analytics", "post", {"question": "Count visible tickets"}),
        ("/api/auth/logout", "post", None),
        ("/api/conversations/123e4567-e89b-42d3-a456-426614174000", "get", None),
        (
            "/api/conversations/123e4567-e89b-42d3-a456-426614174000/messages",
            "post",
            {
                "content": "One reader fails.",
                "client_message_id": "123e4567-e89b-42d3-a456-426614174001",
            },
        ),
        ("/api/ticket-drafts/123e4567-e89b-42d3-a456-426614174000", "get", None),
        (
            "/api/tickets",
            "post",
            {
                "draft_id": "123e4567-e89b-42d3-a456-426614174000",
                "draft_revision": 1,
            },
        ),
        ("/api/tickets/SP-L1-OPEN", "get", None),
        (
            "/api/tickets/SP-L1-OPEN/status",
            "patch",
            {
                "status": "Closed",
                "expected_version": 1,
            },
        ),
        ("/api/policies/02_pos_pricing_returns_policy.md%23pos-card-reader-runbook", "get", None),
    ],
)
def test_protected_operations_require_jwt(client, path, method, payload):
    response = client.request(
        method,
        path,
        headers={"Idempotency-Key": "unauthenticated-test-key"},
        **({"json": payload} if payload is not None else {}),
    )
    expect(response, 401, "Error")


@pytest.mark.parametrize(
    "changes,options",
    [
        ({"exp": 1}, {}),
        ({"iss": "other"}, {}),
        ({"aud": "other"}, {}),
        ({"iat": 4102444800}, {}),
        ({}, {"key": "incorrect-test-key"}),
        ({}, {"algorithm": "none"}),
        ({}, {"algorithm": "HS512"}),
        ({}, {"persisted": False}),
        ({}, {"revoked": True}),
    ],
)
def test_invalid_tokens_are_rejected(client, auth, changes, options):
    expect(client.get("/api/me", headers=auth(1, changes=changes, **options)), 401, "Error")


def test_current_employee_level_is_not_a_token_or_browser_override(client, auth, databases):
    headers = auth(4, changes={"escalation_level": 99, "role": "Administrator"})
    with sqlite3.connect(databases["retail"]) as connection:
        connection.execute(
            "UPDATE employee_master SET escalation_level=1 WHERE employee_id=?", (EMPLOYEES[4],)
        )
    body = expect(client.get("/api/me", headers=headers), 200, "EmployeeContext")
    assert body["escalation_level"] == 1


def test_assignment_change_invalidates_old_session(client, auth, databases):
    headers = auth(1)
    with sqlite3.connect(databases["retail"]) as connection:
        connection.execute("UPDATE employee_master SET store_id='ST002' WHERE employee_id='E9001'")
    expect(client.get("/api/me", headers=headers), 401, "Error")


def test_logout_revokes_session(client, auth):
    headers = auth(1)
    expect(client.get("/api/me", headers=headers), 200, "EmployeeContext")
    expect(client.post("/api/auth/logout", headers=headers), 204)
    expect(client.get("/api/me", headers=headers), 401, "Error")
