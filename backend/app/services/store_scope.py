"""Assigned-store authorization for reporting, independent of ticket-read visibility."""

import re

from app.storage import fail


def require_assigned_store(employee, requested_store=None):
    assigned = employee["assigned_store_id"]
    if requested_store is not None and requested_store != assigned:
        fail(403, "You can only report issues for your assigned store")
    return assigned


def mentions_another_store(text, assigned_store):
    return bool(
        {value.upper() for value in re.findall(r"\b(?:ST|WH)[0-9]{3}\b", text, re.I)}
        - {assigned_store}
    )
