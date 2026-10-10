"""HS256 JWT sessions with exact claims, directory revalidation and persisted revocation."""

import base64
import hashlib
import hmac
import json
import os
import secrets

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.storage import directory, employee_context, fail, now, state, uid

bearer = HTTPBearer(auto_error=False, scheme_name="BearerJWT")
# A development key is process-local: restarting invalidates existing development tokens.
DEV_SECRET = secrets.token_bytes(32)


def secret():
    configured = os.getenv("JWT_SECRET")
    if configured and len(configured.encode()) < 32:
        fail(503, "JWT_SECRET must contain at least 32 bytes")
    if os.getenv("APP_ENV") == "production" and not configured:
        fail(503, "JWT_SECRET is required in production")
    return configured.encode() if configured else DEV_SECRET


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def decode(value):
    return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)


def issue(employee):
    timestamp = int(now().timestamp())
    claims = dict(
        sub=employee["employee_id"],
        store_id=employee["store_id"],
        iss="storepilot",
        aud="storepilot-api",
        iat=timestamp,
        exp=timestamp + 1800,
        jti=uid(),
    )
    prefix = encode(b'{"alg":"HS256","typ":"JWT"}') + "." + encode(json.dumps(claims).encode())
    token = prefix + "." + encode(hmac.new(secret(), prefix.encode(), hashlib.sha256).digest())
    with state() as db:
        db.execute(
            "INSERT INTO sessions(digest,employee,store,expires) VALUES (?,?,?,?)",
            (digest(claims["jti"]), claims["sub"], claims["store_id"], claims["exp"]),
        )
    return token, claims


def current(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not credentials or credentials.scheme.lower() != "bearer":
        fail(401, "Invalid or expired session")
    key = secret()
    try:
        if len(credentials.credentials) > 8192:
            raise ValueError()
        header, body, signature = credentials.credentials.split(".")
        if json.loads(decode(header)) != {"alg": "HS256", "typ": "JWT"}:
            raise ValueError()
        expected = hmac.new(key, f"{header}.{body}".encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, decode(signature)):
            raise ValueError()
        claims = json.loads(decode(body))
        if not isinstance(claims, dict) or any(
            not isinstance(claims.get(field), str)
            for field in ("sub", "store_id", "iss", "aud", "jti")
        ):
            raise ValueError()
        ts = now().timestamp()
        if (
            claims["iss"] != "storepilot"
            or claims["aud"] != "storepilot-api"
            or type(claims["iat"]) is not int
            or type(claims["exp"]) is not int
            or claims["exp"] - claims["iat"] != 1800
            or claims["iat"] > ts + 30
            or claims["exp"] <= ts - 30
            or not isinstance(claims["jti"], str)
        ):
            raise ValueError()
    except (ValueError, KeyError, TypeError, UnicodeError):
        fail(401, "Invalid or expired session")
    with state() as db:
        session = db.execute(
            "SELECT * FROM sessions WHERE digest=?", (digest(claims["jti"]),)
        ).fetchone()
    employee = directory().get(claims["sub"])
    if (
        not session
        or session["revoked"]
        or session["expires"] <= ts - 30
        or session["employee"] != claims["sub"]
        or session["store"] != claims["store_id"]
        or not employee
        or employee["store_id"] != claims["store_id"]
    ):
        fail(401, "Invalid or expired session")
    request.state.session_digest = digest(claims["jti"])
    return employee_context(employee)


def rate_limit(key, maximum, seconds=60):
    exceeded = False
    with state() as db:
        ts = now().timestamp()
        row = db.execute("SELECT * FROM rate_limits WHERE key=?", (key,)).fetchone()
        if not row or ts - row["starts"] >= seconds:
            db.execute("INSERT OR REPLACE INTO rate_limits VALUES (?,?,1)", (key, ts))
        elif row["count"] >= maximum:
            exceeded = True
        else:
            db.execute("UPDATE rate_limits SET count=count+1 WHERE key=?", (key,))
    if exceeded:
        from fastapi import HTTPException

        raise HTTPException(
            429, "Request rate limit exceeded", headers={"Retry-After": str(seconds)}
        )
