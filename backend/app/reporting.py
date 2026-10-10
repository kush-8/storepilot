"""Shared current-directory visibility and time filters for tickets and aggregates."""

import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta

from app.copilot import sanitize
from app.models import Filters
from app.storage import ANCHOR, directory, fail, now, source, state


def historical():
    with source() as db:
        cases = [dict(r) for r in db.execute("SELECT * FROM support_cases")]
    results = []
    for row in cases:
        timestamp = (
            datetime.fromisoformat(row["created_ts"]).replace(tzinfo=ANCHOR.tzinfo).isoformat()
        )
        text, _ = sanitize(row["issue_text"])
        results.append(
            dict(
                ticket_id=row["case_id"],
                title=text[:200],
                description=text,
                created_by_employee_id=row["employee_id"],
                creator_current_level=0,
                affected_store_id=row["store_id"],
                sku=row["sku"],
                register_id=row["register_id"],
                category=row["category_label"],
                priority=row["priority_label"],
                status=row["status"],
                confidence=None,
                review_required=False,
                approval_required=False,
                approval_status="not_required",
                origin="historical_import",
                priority_provenance="historical_label",
                policy_validation_status="unvalidated",
                created_at=timestamp,
                updated_at=timestamp,
                closed_at=None,
                version=1,
                recommendations=[],
                citations=[],
                evidence=[],
                escalation=None,
                events=[],
            )
        )
    return results


def visible(items, employee):
    employees = directory()
    result = []
    for ticket in items:
        creator = employees.get(ticket["created_by_employee_id"])
        if creator and creator["escalation_level"] <= employee["escalation_level"]:
            ticket["creator_current_level"] = creator["escalation_level"]
            result.append(ticket)
    return result


def detail(ticket_id, employee, db=None):
    if db is None:
        with state() as connection:
            return detail(ticket_id, employee, connection)
    row = db.execute(
        "SELECT payload FROM records WHERE kind='ticket' AND id=?", (ticket_id,)
    ).fetchone()
    items = (
        [json.loads(row[0])] if row else [t for t in historical() if t["ticket_id"] == ticket_id]
    )
    allowed = visible(items, employee)
    if not allowed:
        fail(404, "Resource not found")
    return allowed[0]


def summary(ticket):
    return {
        k: v
        for k, v in ticket.items()
        if k
        not in ("register_id", "recommendations", "citations", "evidence", "escalation", "events")
    }


def query(filters: Filters, employee, search=None):
    end = filters.end or (ANCHOR if filters.data_mode == "historical_snapshot" else now())
    window = filters.window or "last7d"
    start = filters.start or (
        end - timedelta(days={"last24h": 1, "last7d": 7, "last30d": 30}[window])
        if window != "all"
        else None
    )
    if filters.data_mode == "historical_snapshot":
        items = historical()
    else:
        with state() as db:
            items = [
                json.loads(r[0])
                for r in db.execute("SELECT payload FROM records WHERE kind='ticket'")
            ]
    items = visible(items, employee)
    matching = []
    for ticket in items:
        created = datetime.fromisoformat(ticket["created_at"])
        if created > end or (start and created <= start):
            continue
        if any(
            value and ticket[field] != value
            for field, value in (
                ("affected_store_id", filters.store_id),
                ("sku", filters.sku),
                ("status", filters.status),
                ("priority", filters.priority),
                ("category", filters.category),
            )
        ):
            continue
        if search and search.lower() not in (ticket["title"] + " " + ticket["description"]).lower():
            continue
        matching.append(ticket)
    matching.sort(key=lambda ticket: (ticket["created_at"], ticket["ticket_id"]), reverse=True)
    serialized = filters.model_dump(mode="json", exclude_none=True)
    if not filters.start:
        serialized["window"] = window
    with source() as db:
        hashes = dict(db.execute("SELECT table_name,source_sha256 FROM import_manifest"))
    context = dict(
        scope=dict(
            viewer_employee_id=employee["employee_id"],
            viewer_current_level=employee["escalation_level"],
            rule="creator_current_level <= viewer_current_level",
        ),
        filters=serialized,
        time_window=dict(
            start=start.isoformat() if start else None,
            end=end.isoformat(),
            interval="(start,end]",
            timezone="Asia/Kolkata",
        ),
        source_versions=hashes,
    )
    revision = hashlib.sha256(json.dumps(matching, sort_keys=True).encode()).hexdigest()
    return matching, context, revision


def dashboard_data(items, context, revision):
    counts = Counter(t["status"] for t in items)
    unresolved = [t for t in items if t["status"] != "Closed"]

    def buckets(field):
        return [
            dict(label=key, count=value)
            for key, value in sorted(Counter(t[field] for t in items).items())
        ]

    return dict(
        context=context,
        metrics=dict(
            total=len(items),
            open=counts["Open"],
            in_progress=counts["In Progress"],
            closed=counts["Closed"],
            unresolved=len(unresolved),
            p1_unresolved=sum(t["priority"] == "P1" for t in unresolved),
            p2_unresolved=sum(t["priority"] == "P2" for t in unresolved),
        ),
        by_priority=buckets("priority"),
        by_category=buckets("category"),
        by_store=buckets("affected_store_id"),
        data_revision=revision,
    )
