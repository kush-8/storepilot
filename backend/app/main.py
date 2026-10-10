"""StorePilot API implementing the supplied OpenAPI contract."""

import hashlib
import json
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Path, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.auth import current, directory, employee_context, issue, rate_limit
from app.copilot import message, policies, sanitize, triage, unsafe
from app.models import (
    AnalyticsRequest,
    ConversationCreate,
    Filters,
    LoginRequest,
    MessageRequest,
    StatusUpdate,
    TicketCreate,
)
from app.reporting import dashboard_data, detail, query, summary
from app.storage import (
    ROOT,
    check_reference,
    fail,
    get_record,
    now,
    put_record,
    source,
    state,
    uid,
)

app = FastAPI(title="StorePilot API", version="2.0.0")
Employee = Annotated[dict, Depends(current)]


def query_filters(request: Request):
    fields = {k: v for k, v in request.query_params.items() if k in Filters.model_fields}
    unknown = set(request.query_params) - set(Filters.model_fields) - {"search", "limit", "offset"}
    if unknown:
        fail(422, "Unknown query parameter")
    try:
        return Filters.model_validate(fields)
    except ValidationError:
        fail(422, "Invalid filters or time range")


@app.middleware("http")
async def request_id(request, call_next):
    request.state.request_id = uid()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    codes = {
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "validation_error",
        429: "rate_limited",
        503: "unavailable",
        504: "timeout",
    }
    return JSONResponse(
        dict(
            code=codes.get(exc.status_code, "error"),
            message=str(exc.detail),
            request_id=request.state.request_id,
        ),
        status_code=exc.status_code,
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return JSONResponse(
        dict(
            code="validation_error",
            message="Invalid request body or parameters",
            request_id=request.state.request_id,
        ),
        status_code=422,
    )


@app.get("/api/health")
def health():
    capabilities = dict(
        source_database="unavailable",
        application_database="unavailable",
        chat="unavailable",
        retrieval="unavailable",
    )
    try:
        with source() as db:
            for table in (
                "employee_master",
                "store_master",
                "support_cases",
                "inventory",
                "product_master",
                "escalation_matrix",
                "import_manifest",
            ):
                db.execute(f"SELECT 1 FROM {table} LIMIT 1")
        capabilities["source_database"] = "ready"
    except HTTPException:
        pass
    try:
        with state():
            pass
        capabilities["application_database"] = "ready"
    except HTTPException:
        pass
    if policies():
        capabilities["retrieval"] = "ready"
    if all(
        capabilities[k] == "ready" for k in ("source_database", "application_database", "retrieval")
    ):
        capabilities["chat"] = "ready"
    unavailable = any(
        capabilities[k] != "ready" for k in ("source_database", "application_database")
    )
    status = (
        "unavailable"
        if unavailable
        else ("ok" if all(v == "ready" for v in capabilities.values()) else "degraded")
    )
    return JSONResponse(
        dict(status=status, capabilities=capabilities), status_code=503 if unavailable else 200
    )


@app.post("/api/auth/login")
def login(body: LoginRequest, request: Request):
    rate_limit("login:" + (request.client.host if request.client else "local"), 20)
    employee = directory().get(body.employee_id)
    if not employee or employee["store_id"] != body.store_id:
        fail(401, "Invalid employee or store")
    token, claims = issue(employee)
    return dict(
        access_token=token,
        token_type="Bearer",
        expires_in=1800,
        expires_at=datetime.fromtimestamp(claims["exp"], timezone.utc).isoformat(),
        employee=employee_context(employee),
    )


@app.post("/api/auth/logout", status_code=204)
def logout(request: Request, employee: Employee):
    with state() as db:
        db.execute("UPDATE sessions SET revoked=1 WHERE digest=?", (request.state.session_digest,))
    return Response(status_code=204)


@app.get("/api/me")
def me(employee: Employee):
    return employee


@app.get("/api/stores")
def stores(employee: Employee):
    with source() as db:
        return dict(
            items=[
                dict(
                    store_id=r["store_id"],
                    store_name=r["store_name"],
                    city=r["city"],
                    region=r["region"],
                    location_type="warehouse" if r["store_id"].startswith("WH") else "store",
                )
                for r in db.execute("SELECT * FROM store_master")
            ]
        )


@app.post("/api/conversations", status_code=201)
def create_conversation(body: ConversationCreate, employee: Employee):
    check_reference(body.affected_store_id)
    conversation = dict(
        conversation_id=uid(),
        owner_employee_id=employee["employee_id"],
        affected_store_id=body.affected_store_id or employee["assigned_store_id"],
        created_at=now().isoformat(),
        updated_at=now().isoformat(),
        messages=[],
    )
    with state() as db:
        put_record(
            db,
            "conversation",
            conversation["conversation_id"],
            employee["employee_id"],
            conversation,
        )
    return conversation


def public_conversation(data):
    return {
        k: v
        for k, v in data.items()
        if k not in ("draft_revision", "latest_draft_id", "issue_context")
    }


@app.get("/api/conversations/{conversation_id}")
def get_conversation(conversation_id: UUID, employee: Employee):
    with state() as db:
        return public_conversation(
            get_record(db, "conversation", conversation_id, employee["employee_id"])
        )


@app.post("/api/conversations/{conversation_id}/messages")
def send_message(conversation_id: UUID, body: MessageRequest, employee: Employee):
    rate_limit("chat:" + employee["employee_id"], 30)
    owner = employee["employee_id"]
    clean, _ = sanitize(body.content)
    # Only sanitized request digests are retained, never raw sensitive content.
    context = body.context.model_dump(exclude_none=True)
    if "register_id" in context:
        context["register_id"] = sanitize(context["register_id"])[0]
    digest = hashlib.sha256(json.dumps([clean, context], sort_keys=True).encode()).hexdigest()
    check_reference(context.get("affected_store_id"), context.get("sku"))
    with state() as db:
        conversation = get_record(db, "conversation", conversation_id, owner)
        cached = db.execute(
            "SELECT * FROM turns WHERE conversation_id=? AND client_id=?",
            (str(conversation_id), str(body.client_message_id)),
        ).fetchone()
        if cached:
            if cached["digest"] != digest:
                fail(409, "Message ID already used with different content")
            return json.loads(cached["payload"])
        previous = conversation.get("issue_context", {})
        previous.update(context)
        # Follow-up classifications use sanitized prior user turns (bounded to request limit).
        history = [m["content"] for m in conversation["messages"] if m["role"] == "user"]
        combined = (" ".join(history[-4:]) + " " + clean).strip()[-4000:]
        _, turn = triage(conversation, combined, previous)
        turn["guardrails"]["pii_detected"] = sanitize(body.content)[1]
        draft = turn["ticket_draft"]
        if conversation.get("latest_draft_id"):
            old = get_record(db, "draft", conversation["latest_draft_id"], owner)
            old["generation_allowed"] = False
            put_record(db, "draft", old["draft_id"], owner, old)
        if draft:
            put_record(db, "draft", draft["draft_id"], owner, draft)
            conversation["latest_draft_id"] = draft["draft_id"]
        else:
            conversation.pop("latest_draft_id", None)
        conversation["messages"].extend([message("user", clean), turn["assistant_message"]])
        conversation["updated_at"] = now().isoformat()
        conversation["issue_context"] = previous
        conversation["affected_store_id"] = previous.get(
            "affected_store_id", conversation["affected_store_id"]
        )
        put_record(db, "conversation", conversation_id, owner, conversation)
        db.execute(
            "INSERT INTO turns VALUES (?,?,?,?)",
            (str(conversation_id), str(body.client_message_id), digest, json.dumps(turn)),
        )
        return turn


@app.get("/api/ticket-drafts/{draft_id}")
def get_draft(draft_id: UUID, employee: Employee):
    with state() as db:
        draft = get_record(db, "draft", draft_id, employee["employee_id"])
        if datetime.fromisoformat(draft["expires_at"]) <= now():
            draft["generation_allowed"] = False
        return draft


@app.post("/api/tickets", status_code=201)
def create_ticket(
    body: TicketCreate,
    employee: Employee,
    response: Response,
    idempotency_key: Annotated[str, Header(min_length=8, max_length=128)],
):
    owner = employee["employee_id"]
    digest = hashlib.sha256(body.model_dump_json().encode()).hexdigest()
    with state() as db:
        receipt = db.execute(
            "SELECT * FROM receipts WHERE owner=? AND key=?", (owner, idempotency_key)
        ).fetchone()
        if receipt:
            if receipt["digest"] != digest:
                fail(409, "Idempotency key already used with different payload")
            response.status_code = 200
            return dict(ticket=detail(receipt["ticket_id"], employee, db), idempotent_replay=True)
        draft = get_record(db, "draft", body.draft_id, owner)
        if (
            not draft["generation_allowed"]
            or draft["revision"] != body.draft_revision
            or datetime.fromisoformat(draft["expires_at"]) <= now()
        ):
            fail(409, "Draft is stale, expired or already committed")
        for citation in draft["citations"]:
            section = policies().get(citation["section_id"])
            if not section or section["source_hash"] != citation["source_hash"]:
                fail(409, "Policy source changed; generate a new draft")
        check_reference(draft["affected_store_id"], draft["sku"])
        timestamp = now().isoformat()
        ticket = {
            k: draft[k]
            for k in (
                "title",
                "description",
                "affected_store_id",
                "sku",
                "register_id",
                "category",
                "priority",
                "confidence",
                "recommendations",
                "citations",
                "evidence",
                "escalation",
                "review_required",
                "approval_required",
            )
        }
        ticket.update(
            ticket_id="TKT-" + uid(),
            created_by_employee_id=owner,
            creator_current_level=employee["escalation_level"],
            status="Open",
            origin="copilot",
            approval_status="pending" if draft["approval_required"] else "not_required",
            priority_provenance="policy_validated",
            policy_validation_status="validated",
            created_at=timestamp,
            updated_at=timestamp,
            closed_at=None,
            version=1,
            events=[
                dict(
                    event_id=uid(),
                    event_type="created",
                    actor_employee_id=owner,
                    old_status=None,
                    new_status="Open",
                    note=None,
                    created_at=timestamp,
                )
            ],
        )
        put_record(db, "ticket", ticket["ticket_id"], owner, ticket)
        db.execute(
            "INSERT INTO receipts VALUES (?,?,?,?,?)",
            (owner, idempotency_key, digest, ticket["ticket_id"], str(body.draft_id)),
        )
        draft["generation_allowed"] = False
        put_record(db, "draft", body.draft_id, owner, draft)
        return dict(ticket=ticket, idempotent_replay=False)


@app.get("/api/tickets")
def list_tickets(
    employee: Employee,
    filters: Annotated[Filters, Depends(query_filters)],
    search: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    items, context, _ = query(filters, employee, search)
    return dict(
        items=[summary(t) for t in items[offset : offset + limit]],
        total=len(items),
        limit=limit,
        offset=offset,
        context=context,
    )


@app.get("/api/tickets/{ticket_id}")
def get_ticket(ticket_id: Annotated[str, Path(min_length=1, max_length=80)], employee: Employee):
    return detail(ticket_id, employee)


@app.patch("/api/tickets/{ticket_id}/status")
def update_status(ticket_id: str, body: StatusUpdate, employee: Employee):
    with state() as db:
        ticket = detail(ticket_id, employee, db)
        if ticket["created_by_employee_id"] != employee["employee_id"]:
            fail(403, "Only the ticket creator may update status")
        if ticket["origin"] == "historical_import":
            fail(409, "Historical snapshot is immutable")
        if body.expected_version != ticket["version"] or body.status == ticket["status"]:
            fail(409, "Stale version or invalid status transition")
        if ticket["status"] == "Closed" and (body.status != "Open" or not body.reason):
            fail(409, "Reopen to Open with a reason")
        timestamp = now().isoformat()
        ticket["events"].append(
            dict(
                event_id=uid(),
                event_type="status_changed",
                actor_employee_id=employee["employee_id"],
                old_status=ticket["status"],
                new_status=body.status,
                note=sanitize(body.reason)[0] if body.reason else None,
                created_at=timestamp,
            )
        )
        ticket.update(
            status=body.status,
            updated_at=timestamp,
            version=ticket["version"] + 1,
            closed_at=timestamp if body.status == "Closed" else None,
        )
        put_record(db, "ticket", ticket_id, employee["employee_id"], ticket)
        return ticket


@app.get("/api/dashboard")
def dashboard(employee: Employee, filters: Annotated[Filters, Depends(query_filters)]):
    return dashboard_data(*query(filters, employee))


@app.post("/api/dashboard/analytics")
def analytics(body: AnalyticsRequest, employee: Employee):
    rate_limit("analytics:" + employee["employee_id"], 30)
    clean, pii = sanitize(body.question)
    thread_id = str(body.analytics_thread_id or uid())
    with state() as db:
        if body.analytics_thread_id:
            get_record(db, "analytics", thread_id, employee["employee_id"])
        put_record(db, "analytics", thread_id, employee["employee_id"], dict(question=clean))
    items, context, _ = query(body.filters, employee)
    refusal = unsafe(clean)
    supported = any(
        word in clean.lower()
        for word in (
            "ticket",
            "case",
            "unresolved",
            "priority",
            "category",
            "store",
            "count",
            "open",
            "closed",
        )
    )
    chosen = (
        [t for t in items if t["status"] != "Closed"] if "unresolved" in clean.lower() else items
    )
    requested_priorities = [p for p in ("P1", "P2", "P3", "P4") if p.lower() in clean.lower()]
    if requested_priorities:
        chosen = [t for t in chosen if t["priority"] in requested_priorities]
    from collections import Counter

    field = (
        "affected_store_id"
        if "store" in clean.lower()
        else ("category" if "category" in clean.lower() else "priority")
    )
    rows = [dict(label=k, count=v) for k, v in sorted(Counter(t[field] for t in chosen).items())]
    if refusal or not supported:
        rows = []
    return dict(
        request_id=uid(),
        analytics_thread_id=thread_id,
        result_type="refusal" if refusal else ("answer" if supported else "unsupported"),
        answer="Restricted data requests are refused."
        if refusal
        else (
            f"{len(chosen)} authorized tickets match; grouped by {field}."
            if supported
            else "Supported analytics: ticket counts by store, category or priority. "
            "Use filters for dates and status."
        ),
        follow_up_question=None,
        intent="ticket_counts" if supported and not refusal else None,
        context=context,
        columns=[
            dict(key="label", label=field, value_type="string"),
            dict(key="count", label="Tickets", value_type="number"),
        ],
        rows=rows[:200],
        total_rows=len(rows),
        truncated=len(rows) > 200,
        query_template_ids=["authorized_ticket_counts"] if rows else [],
        citations=[],
        evidence=[],
        guardrails=dict(
            pii_checked=True,
            pii_detected=pii,
            safety_refusal=refusal,
            human_review_required=refusal,
        ),
        limitations=["Local template analytics; use explicit filters for date ranges and status."],
    )


@app.get("/api/policies/{section_id}")
def policy(section_id: str, employee: Employee):
    section = policies().get(section_id)
    if not section:
        fail(404, "Resource not found")
    return section


def contract():
    # Requests and returned objects are checked against this contract in the integration suite.
    schema = json.loads((ROOT / "openapi.json").read_text(encoding="utf-8"))
    schema["info"]["title"] = "StorePilot API"
    schema["info"]["description"] = (
        "Implemented local retail operations API. Prototype ID/store login. "
        "Rule-based policy Copilot."
    )
    schema["x-implementation-status"] = "implemented-local"
    return schema


app.openapi = contract
