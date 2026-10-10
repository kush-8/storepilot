"""Local policy retrieval and conservative deterministic triage; no external actions."""

import hashlib
import re
from datetime import timedelta

from app.storage import ROOT, now, source, uid


def sanitize(text):
    original = text
    text = re.sub(r"\b(?:\d[ -]?){13,19}\b", "[REDACTED_CARD]", text)
    text = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "[REDACTED_EMAIL]", text)
    text = re.sub(r"(?<!\w)(?:\+\d{1,3}[ -]?)?\d{10,12}(?!\w)", "[REDACTED_PHONE]", text)
    text = re.sub(
        r"\b(cvv|pin|otp|password|account(?: number)?|aadhaar|pan|token|secret)\s*[:=]?\s+\S+",
        r"\1 [REDACTED]",
        text,
        flags=re.I,
    )
    return text, text != original


def unsafe(text):
    return bool(
        re.search(
            r"ignore (?:all |the |previous |system )*instructions|"
            r"reveal.*(?:prompt|hidden|test cases)|"
            r"(?:show|give|print|export|reveal|send|list|access).*(?:card numbers?|cvv|password|"
            r"credentials|customer database|private.*records|payment tokens|"
            r"supplier pric|contracts)|"
            r"bypass.*(?:safety|rules|controls)|invent.*policy",
            text,
            re.I,
        )
    )


def policies():
    sections = {}
    for path in sorted((ROOT / "knowledge_base").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        source_hash = hashlib.sha256(text.encode()).hexdigest()
        for match in re.finditer(r"^## ([^\n]+)\n(.*?)(?=^## |\Z)", text, re.M | re.S):
            heading, body = match.groups()
            slug = re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")
            section_id = path.name + "#" + slug
            sections[section_id] = dict(
                section_id=section_id,
                filename=path.name,
                heading=heading,
                body=body.strip(),
                source_hash=source_hash,
            )
    return sections


def retrieve(text, filenames=None):
    tokens = set(re.findall(r"[a-z]{3,}", text.lower()))
    ranked = []
    for section in policies().values():
        if filenames and section["filename"] not in filenames:
            continue
        words = set(re.findall(r"[a-z]{3,}", (section["heading"] + " " + section["body"]).lower()))
        score = len(tokens & words)
        if score:
            ranked.append((score, section))
    ranked.sort(key=lambda item: (-item[0], item[1]["section_id"]))
    return [section for _, section in ranked[:3]]


def message(role, content):
    return dict(
        message_id=uid(),
        role=role,
        content=content[:12000],
        created_at=now().isoformat(),
        pii_checked=True,
    )


def triage(conversation, text, context):
    clean, pii = sanitize(text)
    # Classify against sanitized text only. Retrieved documents remain data, never instructions.
    low = clean.lower()
    flags = dict(
        pii_checked=True,
        pii_detected=pii,
        safety_refusal=unsafe(clean),
        human_review_required=False,
    )
    result = dict(
        request_id=uid(),
        conversation_id=conversation["conversation_id"],
        assistant_message=None,
        result_type="unsupported",
        route="Unsupported",
        follow_up_question=None,
        category=None,
        priority=None,
        recommendations=[],
        citations=[],
        evidence=[],
        escalation=None,
        guardrails=flags,
        ticket_draft=None,
        limitations=[
            "Local rule-based triage; no OpenAI model is called.",
            "Recommendations require human execution; root cause is not confirmed.",
        ],
    )
    if flags["safety_refusal"]:
        result.update(result_type="refusal", route="Refuse")
        result["guardrails"]["human_review_required"] = True
        answer = (
            "I cannot disclose restricted data or bypass controls. Contact Security/POS Support."
        )
    elif re.search(r"\b(dashboard|analytics|how many|count tickets|tickets by|reporting)\b", low):
        result.update(result_type="dashboard_redirect", route="Dashboard")
        answer = "Use Dashboard Analytics for authorized ticket counts and breakdowns."
    else:
        categories = [
            (
                "Product Quality and Safety",
                r"injur|recall|unsafe|quality|cracked|damag|malfunction",
            ),
            ("Returns and Refunds", r"refund|return|receipt missing"),
            ("Pricing and Promotions", r"pric|promotion|shelf label"),
            ("POS and Payments", r"register|card reader|payment|\bpos\b|terminal"),
            ("Vendor and Supply Chain", r"vendor|shipment|delivery|supplier|short ship"),
            ("Inventory and Replenishment", r"inventory|stock|reorder|quantity|replenish"),
            ("Customer Service", r"customer|complaint|service"),
        ]
        category = next((cat for cat, pattern in categories if re.search(pattern, low)), None)
        store = context.get("affected_store_id") or conversation["affected_store_id"]
        sku = context.get("sku")
        if not category or not store:
            result.update(
                result_type="clarification",
                route="Clarify",
                follow_up_question="Which store is affected, what failed, and what is the impact?",
            )
            answer = result["follow_up_question"]
        else:
            priority = "P3"
            if re.search(
                r"injur|recall|unsafe|all registers|entire store|store.wide|all.*payments", low
            ):
                priority = "P1"
            elif re.search(r"repeated|many customers|many skus|multiple|short ship|stock.out", low):
                priority = "P2"
            elif re.search(r"\bpolicy\b|how (?:do|should)|what is|guidance", low):
                priority = "P4"
            source_files = {
                "POS and Payments": "02_pos_pricing_returns_policy.md",
                "Pricing and Promotions": "02_pos_pricing_returns_policy.md",
                "Returns and Refunds": "02_pos_pricing_returns_policy.md",
                "Customer Service": "02_pos_pricing_returns_policy.md",
                "Inventory and Replenishment": "03_inventory_replenishment_policy.md",
                "Vendor and Supply Chain": "04_vendor_quality_policy.md",
                "Product Quality and Safety": "04_vendor_quality_policy.md",
            }
            allowed_headings = {
                "POS and Payments": {"POS Card Reader Runbook"},
                "Pricing and Promotions": {"Pricing and Promotions"},
                "Returns and Refunds": {"Returns and Refunds"},
                "Customer Service": {"Customer Recovery"},
                "Inventory and Replenishment": {
                    "Stock-Outs and Replenishment",
                    "Inventory Discrepancy",
                    "Transfer and Reorder Recommendation",
                },
                "Vendor and Supply Chain": {
                    "Short Shipments",
                    "Vendor Performance",
                    "Damaged Goods and Claims",
                },
                "Product Quality and Safety": {
                    "Product Quality Complaints",
                    "Recall and Safety",
                },
            }
            sections = [
                s
                for s in retrieve(clean, [source_files[category]])
                if s["heading"] in allowed_headings[category]
            ]
            if not sections:
                sections = [
                    s
                    for s in policies().values()
                    if s["filename"] == source_files[category]
                    and s["heading"] in allowed_headings[category]
                ][:3]
            if not sections:
                result.update(result_type="unavailable")
                answer = (
                    "No supporting policy section is available. Ask a manager to review this issue."
                )
            else:
                priority_section = policies().get("01_retail_operations_sop.md#priority-rules")
                citation_sections = sections + ([priority_section] if priority_section else [])
                citations = [
                    {k: s[k] for k in ("section_id", "filename", "heading", "source_hash")}
                    for s in citation_sections
                ]
                # Quote bounded policy recommendations; do not invent approval or completed actions.
                steps = []
                for section in sections:
                    steps.extend(re.findall(r"^- (.+)$", section["body"], re.M))
                if not steps:
                    steps = [sections[0]["body"].split("\n\n")[0][:1800]]
                evidence = []
                if sku:
                    with source() as db:
                        inv = db.execute(
                            "SELECT i.*,p.high_demand FROM inventory i "
                            "JOIN product_master p USING(sku) WHERE store_id=? AND sku=?",
                            (store, sku),
                        ).fetchone()
                    if inv:
                        evidence.append(
                            dict(
                                source="inventory",
                                record_ids=[f"{store}/{sku}"],
                                summary=(
                                    f"Snapshot on hand {inv['on_hand']}; "
                                    f"system {inv['system_qty']}; "
                                    f"reorder point {inv['reorder_point']}; "
                                    f"count {inv['last_count_date']}."
                                ),
                                query_template_id="inventory_by_store_sku",
                            )
                        )
                        if category == "Inventory and Replenishment":
                            if inv["on_hand"] == 0 and inv["high_demand"]:
                                priority = "P2"
                approval = priority == "P1" or category in (
                    "Returns and Refunds",
                    "Vendor and Supply Chain",
                    "Product Quality and Safety",
                )
                with source() as db:
                    route = db.execute(
                        "SELECT * FROM escalation_matrix WHERE category=? "
                        "AND priority=? ORDER BY trigger LIMIT 1",
                        (category, priority),
                    ).fetchone()
                escalates = approval or priority == "P2"
                escalation = dict(
                    required=escalates,
                    team=route["team"] if route and escalates else None,
                    channel=route["channel"] if route and escalates else None,
                    sla_minutes=route["sla_minutes"] if route and escalates else None,
                    reason="Human policy review required" if escalates else "Routine guidance",
                    human_approval_required=approval,
                )
                if priority == "P1":
                    steps.insert(
                        0, "Immediately contact Store Manager and the relevant support team."
                    )
                # Ambiguous POS scope cannot become an authoritative ticket classification.
                ambiguous = category == "POS and Payments" and not re.search(
                    r"\bone\b|\bsingle\b|\ball\b|multiple|entire|store.wide", low
                )
                result.update(
                    result_type="clarification" if ambiguous else "recommendation",
                    route="Clarify" if ambiguous else ("Both" if evidence else "RAG"),
                    category=category,
                    priority=None if ambiguous else priority,
                    recommendations=steps[:6],
                    citations=citations,
                    evidence=evidence,
                    escalation=escalation,
                )
                flags["human_review_required"] = approval or ambiguous
                answer = " ".join(result["recommendations"])
                if ambiguous:
                    result["follow_up_question"] = (
                        "Is one register affected or are all registers down?"
                    )
                    answer = result["follow_up_question"]
                elif priority != "P4":
                    revision = conversation.get("draft_revision", 0) + 1
                    conversation["draft_revision"] = revision
                    draft = dict(
                        draft_id=uid(),
                        conversation_id=conversation["conversation_id"],
                        revision=revision,
                        title=f"{category}: {clean[:140]}",
                        description=clean,
                        affected_store_id=store,
                        sku=sku,
                        register_id=context.get("register_id"),
                        category=category,
                        priority=priority,
                        confidence=0.65,
                        recommendations=result["recommendations"],
                        citations=citations,
                        evidence=evidence,
                        escalation=escalation,
                        review_required=approval,
                        approval_required=approval,
                        validation_status="validated",
                        generation_allowed=True,
                        expires_at=(now() + timedelta(minutes=30)).isoformat(),
                    )
                    result["ticket_draft"] = draft
    result["assistant_message"] = message("assistant", answer)
    return clean, result
