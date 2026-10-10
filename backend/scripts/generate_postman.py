"""Generate an ordered, repeatable Postman v2.1 workflow covering every API operation."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def request(name, method, path, status=200, body=None, script="", public=False, headers=None):
    tests = [f'pm.test("HTTP {status}", () => pm.response.to.have.status({status}));']
    if script:
        tests.extend(script.splitlines())
    item = dict(
        name=name,
        request=dict(
            method=method,
            header=[{"key": "Content-Type", "value": "application/json"}] + (headers or []),
            url="{{base_url}}" + path,
        ),
        event=[dict(listen="test", script=dict(type="text/javascript", exec=tests))],
    )
    if body is not None:
        item["request"]["body"] = dict(
            mode="raw", raw=json.dumps(body, indent=2), options=dict(raw=dict(language="json"))
        )
    if public:
        item["request"]["auth"] = dict(type="noauth")
    return item


def generate():
    items = [
        request("01 Health", "GET", "/api/health", public=True),
        request(
            "02 Login",
            "POST",
            "/api/auth/login",
            public=True,
            body=dict(employee_id="{{employee_id}}", store_id="{{store_id}}"),
            script='pm.environment.set("access_token", pm.response.json().access_token);\n'
            'pm.environment.set("idempotency_key", pm.variables.replaceIn("{{$guid}}"));',
        ),
        request("03 Employee profile", "GET", "/api/me"),
        request("04 Stores", "GET", "/api/stores"),
        request(
            "05 Create conversation",
            "POST",
            "/api/conversations",
            201,
            body=dict(affected_store_id="{{store_id}}"),
            script='pm.environment.set("conversation_id", pm.response.json().conversation_id);',
        ),
        request(
            "06 Send issue and prepare draft",
            "POST",
            "/api/conversations/{{conversation_id}}/messages",
            body=dict(
                content="One register card reader stopped working at 10am, error E42. "
                "Other registers work.",
                client_message_id="{{$guid}}",
                context=dict(register_id="REG-1"),
            ),
            script="const d = pm.response.json().ticket_draft;\n"
            'pm.test("Draft prepared", () => pm.expect(d).to.be.an("object"));\n'
            'if (d) { pm.environment.set("draft_id", d.draft_id); '
            'pm.environment.set("draft_revision", d.revision); '
            'pm.environment.set("policy_section", '
            "encodeURIComponent(d.citations[0].section_id)); }",
        ),
        request("07 Read conversation", "GET", "/api/conversations/{{conversation_id}}"),
        request("08 Read draft", "GET", "/api/ticket-drafts/{{draft_id}}"),
        request(
            "09 Create ticket",
            "POST",
            "/api/tickets",
            201,
            body=dict(draft_id="{{draft_id}}", draft_revision=1),
            headers=[dict(key="Idempotency-Key", value="{{idempotency_key}}")],
            script="const t = pm.response.json().ticket;\n"
            'pm.environment.set("ticket_id", t.ticket_id);\n'
            'pm.environment.set("ticket_version", t.version);',
        ),
        request(
            "10 Replay same ticket save",
            "POST",
            "/api/tickets",
            200,
            body=dict(draft_id="{{draft_id}}", draft_revision=1),
            headers=[dict(key="Idempotency-Key", value="{{idempotency_key}}")],
            script='pm.test("Idempotent replay", () => '
            "pm.expect(pm.response.json().idempotent_replay).to.eql(true));",
        ),
        request("11 List live tickets", "GET", "/api/tickets?window=all&limit=50&offset=0"),
        request("12 Read ticket", "GET", "/api/tickets/{{ticket_id}}"),
        request(
            "13 Update status",
            "PATCH",
            "/api/tickets/{{ticket_id}}/status",
            body=dict(
                status="In Progress", expected_version=1, reason="Investigating the card reader"
            ),
        ),
        request("14 Live dashboard", "GET", "/api/dashboard?window=all"),
        request(
            "15 Historical dashboard",
            "GET",
            "/api/dashboard?data_mode=historical_snapshot&window=all",
        ),
        request(
            "16 Dashboard analytics",
            "POST",
            "/api/dashboard/analytics",
            body=dict(
                question="Show unresolved P1 and P2 tickets by store.",
                filters=dict(data_mode="historical_snapshot", window="all"),
            ),
        ),
        request("17 Open cited policy", "GET", "/api/policies/{{policy_section}}"),
        request("18 Logout", "POST", "/api/auth/logout", 204),
        request("19 Verify revoked session", "GET", "/api/me", 401),
    ]
    collection = dict(
        info=dict(
            name="StorePilot — complete API workflow",
            schema="https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            description="Run in order with the StorePilot Local environment. "
            "New conversation and idempotency key each run.",
        ),
        auth=dict(
            type="bearer", bearer=[dict(key="token", value="{{access_token}}", type="string")]
        ),
        item=items,
    )
    values = dict(
        base_url="http://127.0.0.1:8000",
        employee_id="E0001",
        store_id="ST008",
        access_token="",
        conversation_id="",
        draft_id="",
        draft_revision="1",
        ticket_id="",
        ticket_version="1",
        policy_section="",
        idempotency_key="",
    )
    environment = dict(
        name="StorePilot Local",
        values=[
            dict(key=k, value=v, enabled=True, type="secret" if k == "access_token" else "default")
            for k, v in values.items()
        ],
        _postman_variable_scope="environment",
    )
    output = ROOT / "postman"
    output.mkdir(exist_ok=True)
    (output / "StorePilot.postman_collection.json").write_text(
        json.dumps(collection, indent=2), encoding="utf-8"
    )
    (output / "StorePilot.local.postman_environment.json").write_text(
        json.dumps(environment, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    generate()
