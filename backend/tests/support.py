"""Test fixtures, independent JWT construction, schema checks and dependency doubles."""

from __future__ import annotations

import base64
import hashlib
import hmac
import importlib
import json
import sqlite3
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
SIGNING_KEY = "storepilot-tests-only-signing-key-0123456789abcdef"
SPEC = json.loads((BACKEND / "openapi.json").read_text(encoding="utf-8"))
SCHEMA_ID = "urn:storepilot:openapi-tests"
REGISTRY = Registry().with_resource(
    SCHEMA_ID,
    Resource.from_contents(SPEC, default_specification=DRAFT202012),
)
EMPLOYEES = {level: f"E900{level}" for level in range(1, 5)}
CATEGORY = "POS and Payments"


def assert_schema(value, name):
    validator = Draft202012Validator(
        {"$ref": f"{SCHEMA_ID}#/components/schemas/{name}"},
        registry=REGISTRY,
        format_checker=FormatChecker(),
    )
    errors = sorted(validator.iter_errors(value), key=lambda e: str(e.path))
    assert not errors, "\n".join(f"{list(e.path)}: {e.message}" for e in errors)


def expect(response, status, schema=None):
    assert response.status_code == status, response.text
    if schema is not None:
        assert_schema(response.json(), schema)
    return response.json() if response.content else None


def utc_now():
    return datetime.now(timezone.utc)


def iso(value):
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def make_jwt(claims, algorithm="HS256", key=SIGNING_KEY):
    # This independent signer creates valid and adversarial test tokens, not login code.
    def part(value):
        raw = json.dumps(value, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    header, payload = part({"alg": algorithm, "typ": "JWT"}), part(claims)
    body = f"{header}.{payload}"
    signature = hmac.new(key.encode(), body.encode(), hashlib.sha256).digest()
    encoded = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
    return f"{body}.{encoded}" if algorithm != "none" else f"{body}."


def decode_and_check_jwt(token):
    header, payload, signature = token.split(".")
    expected = hmac.new(
        SIGNING_KEY.encode(), f"{header}.{payload}".encode(), hashlib.sha256
    ).digest()
    actual = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
    assert hmac.compare_digest(actual, expected), "JWT signature does not use the test key"
    parsed_header = json.loads(base64.urlsafe_b64decode(header + "=" * (-len(header) % 4)))
    assert parsed_header["alg"] == "HS256"
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))


def bearer(
    application_path,
    level,
    *,
    changes=None,
    algorithm="HS256",
    key=SIGNING_KEY,
    revoked=False,
    persisted=True,
):
    now = utc_now()
    claims = {
        "sub": EMPLOYEES[level],
        "store_id": f"ST00{level}",
        "iss": "storepilot",
        "aud": "storepilot-api",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=30)).timestamp()),
        "jti": str(uuid4()),
    }
    claims.update(changes or {})
    if persisted:
        with sqlite3.connect(application_path) as connection:
            connection.execute(
                "INSERT INTO auth_sessions VALUES (?, ?, ?, ?, ?, ?)",
                (
                    hashlib.sha256(claims["jti"].encode()).hexdigest(),
                    claims["sub"],
                    claims["store_id"],
                    iso(now),
                    iso(now + timedelta(minutes=30)),
                    iso(now) if revoked else None,
                ),
            )
    return {"Authorization": "Bearer " + make_jwt(claims, algorithm, key)}


def boundary(module_name, attribute):
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        assert not (exc.name == module_name or module_name.startswith(exc.name + ".")), (
            f"TDD boundary missing: implement {module_name}.{attribute}"
        )
        raise
    result = getattr(module, attribute, None)
    assert callable(result), f"TDD boundary missing: implement {module_name}.{attribute}"
    return result


class ScriptedModel:
    """Canned structured model replies; never performs inference or tool execution."""

    def __init__(self):
        self.calls = []
        self.responses = {
            "route": {
                "intent": "report_issue",
                "route": "RAG",
                "category": CATEGORY,
                "priority": "P3",
                "confidence": 0.9,
                "entities": {"store_id": "ST003", "register_id": "REG-01"},
                "impact": "one register",
                "missing_fields": [],
            },
            "compose": {
                "answer": "Use another approved register while checking the affected reader.",
                "title": "Single register reader failure",
                "description": "One reader fails while other registers work.",
                "recommendations": ["Confirm other registers work.", "Re-seat the reader cable."],
                "citations": ["02_pos_pricing_returns_policy.md#pos-card-reader-runbook"],
                "limitations": [],
            },
        }

    def set_response(self, stage, **fields):
        self.responses[stage] = {**self.responses.get(stage, {}), **fields}

    def generate(self, stage, payload):
        self.calls.append((stage, deepcopy(payload)))
        assert stage in self.responses, f"Unscripted model stage: {stage}"
        value = self.responses[stage]
        if isinstance(value, Exception):
            raise value
        return deepcopy(value)


class PolicyDouble:
    def __init__(self):
        self.calls = []
        self.sections = []
        for filename in sorted((BACKEND / "knowledge_base").glob("*.md")):
            body = filename.read_text(encoding="utf-8")
            digest = hashlib.sha256(filename.read_bytes()).hexdigest()
            chunks = body.split("\n## ")[1:]
            for chunk in chunks:
                heading, _, content = chunk.partition("\n")
                import re

                slug = re.sub(r"[^a-z0-9\s-]", "", heading.lower()).replace(" ", "-")
                self.sections.append(
                    {
                        "section_id": f"{filename.name}#{slug}",
                        "filename": filename.name,
                        "heading": heading,
                        "heading_slug": slug,
                        "body": content,
                        "source_hash": digest,
                    }
                )
        self.selected = ["02_pos_pricing_returns_policy.md#pos-card-reader-runbook"]

    def search(self, query, limit=4):
        self.calls.append((query, limit))
        return deepcopy([s for s in self.sections if s["section_id"] in self.selected][:limit])


class DataDouble:
    """Spy with supplied evidence; tests inspect the identity passed into data tools."""

    def __init__(self):
        self.calls = []
        self.result = {
            "rows": [
                {
                    "store_id": "ST002",
                    "sku": "SKU1001",
                    "on_hand": 0,
                    "system_qty": 4,
                    "reorder_point": 10,
                }
            ],
            "evidence": [
                {
                    "source": "inventory",
                    "record_ids": ["ST002/SKU1001"],
                    "summary": "Physical stock 0; system stock 4.",
                    "query_template_id": "sku_stockout",
                }
            ],
            "limitations": [],
        }

    def execute(self, template_id, parameters, viewer_employee_id):
        self.calls.append((template_id, deepcopy(parameters), viewer_employee_id))
        return deepcopy(self.result)
