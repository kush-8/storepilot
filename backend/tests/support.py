"""Test fixtures, independent JWT construction, and schema checks."""

from __future__ import annotations

import base64
import hashlib
import hmac
import importlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

BACKEND = Path(__file__).resolve().parents[1]
SIGNING_KEY = "storepilot-tests-only-signing-key-0123456789abcdef"
SPEC = json.loads((BACKEND / "openapi.json").read_text(encoding="utf-8"))
SCHEMA_ID = "urn:storepilot:openapi-tests"
REGISTRY = Registry().with_resource(
    SCHEMA_ID,
    Resource.from_contents(SPEC, default_specification=DRAFT202012),
)
EMPLOYEES = {level: f"E900{level}" for level in range(1, 5)}


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
                "INSERT INTO sessions VALUES (?, ?, ?, ?, ?)",
                (
                    hashlib.sha256(claims["jti"].encode()).hexdigest(),
                    claims["sub"],
                    claims["store_id"],
                    claims["exp"],
                    int(revoked),
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
