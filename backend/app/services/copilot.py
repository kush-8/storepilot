"""Translate the tested agent graph into safe recommendations and server-held drafts."""

import json
import re
from datetime import timedelta

from app.agents.guardrails import PIIAgent, SafetyAgent
from app.storage import check_reference, now, source, uid

from .messages import message, sanitize
from .policies import policies
from .store_scope import mentions_another_store


def escalation(category, priority, review=False, approval=False):
    required = priority in {"P1", "P2"} or review or approval
    with source() as db:
        row = db.execute(
            "SELECT * FROM escalation_matrix WHERE category=? AND priority=? "
            "ORDER BY trigger LIMIT 1",
            (category, priority),
        ).fetchone()
    return dict(
        required=required,
        team=row["team"] if row and required else None,
        channel=row["channel"] if row and required else None,
        sla_minutes=row["sla_minutes"] if row and required else None,
        reason="Human policy review required" if required else "Routine guidance",
        human_approval_required=approval,
    )


def validated_priority(classification, text, data):
    low = text.lower()
    priority = classification.priority
    if SafetyAgent().evaluate(PIIAgent().sanitize(text)).priority_override == "P1":
        return "P1"
    if re.search(
        r"injur|recall|unsafe|all registers|entire store|store.wide|all.*payments|"
        r"loose.*handlebar|handlebar.*loose",
        low,
    ):
        return "P1"
    if classification.category == "POS and Payments":
        if re.search(r"\b(one|single)\b", low):
            return "P3"
    if classification.category == "Inventory and Replenishment" and data:
        for evidence in data.evidence:
            for row in evidence.rows:
                if row.get("on_hand") == 0 and row.get("high_demand") == 1:
                    return "P2"
    if classification.intent == "incident":
        if re.search(r"repeated|many customers|many skus|multiple|short.ship|stock.out", low):
            return "P2"
        return "P3"
    return priority


class CopilotService:
    def __init__(self, workflow_provider):
        self.workflow_provider = workflow_provider

    def respond(self, conversation, text, context, employee_id):
        pii = PIIAgent().sanitize(text)
        safety = SafetyAgent().evaluate(pii)
        clean = pii.sanitized_text
        turn = dict(
            request_id=uid(),
            conversation_id=conversation["conversation_id"],
            assistant_message=None,
            result_type="unavailable",
            route="Unsupported",
            follow_up_question=None,
            category=None,
            priority=None,
            recommendations=[],
            citations=[],
            evidence=[],
            escalation=None,
            ticket_draft=None,
            guardrails=dict(
                pii_checked=True,
                pii_detected=pii.pii_detected,
                safety_refusal=not safety.allowed,
                human_review_required=False,
            ),
            limitations=[],
        )

        def finish(answer):
            turn["assistant_message"] = message("assistant", answer)
            return turn

        if not safety.allowed:
            turn.update(
                result_type="refusal",
                route="Refuse",
                priority="P1",
                category="Other or Security",
                escalation=escalation("Other or Security", "P1", True),
            )
            turn["guardrails"]["human_review_required"] = True
            return finish(safety.safe_response)
        if re.search(
            r"\b(dashboard|analytics|how many|count tickets|tickets by|reporting|"
            r"unresolved tickets|ticket counts)\b",
            clean,
            re.I,
        ):
            turn.update(result_type="dashboard_redirect", route="Dashboard")
            return finish("Use Dashboard Analytics for authorized ticket counts and breakdowns.")
        # IDs come from validated request context/conversation, never model-invented caller IDs.
        store = context.get("affected_store_id") or conversation["affected_store_id"]
        if mentions_another_store(clean, store):
            question = (
                f"You can only report issues for your assigned store ({store}). "
                "Please describe the issue there."
            )
            turn.update(result_type="clarification", route="Clarify", follow_up_question=question)
            return finish(question)
        extra = " Context: " + json.dumps(
            {
                "store_id": store,
                "sku": context.get("sku"),
                "register_id": context.get("register_id"),
            }
        )
        try:
            result = self.workflow_provider().ask(
                clean[: 4000 - len(extra)] + extra,
                viewer_employee_id=employee_id,
                entity_context={
                    key: value
                    for key, value in {"store_id": store, "sku": context.get("sku")}.items()
                    if value
                },
            )
        except Exception:
            turn["guardrails"]["human_review_required"] = True
            turn["limitations"] = ["Agent runtime unavailable; check model and policy index setup."]
            return finish("Copilot is unavailable. Please retry or contact your Store Manager.")
        turn["guardrails"]["human_review_required"] = result.human_review_required
        turn["limitations"] = result.limitations[:10]
        classification = result.triage
        if classification:
            turn["category"] = classification.category
            turn["priority"] = validated_priority(classification, clean, result.data)
            if classification.entities.sku and not context.get("sku"):
                try:
                    check_reference(sku=classification.entities.sku)
                    context["sku"] = classification.entities.sku
                except Exception:
                    turn["guardrails"]["human_review_required"] = True
                    return finish("The SKU could not be verified. Please check the SKU and retry.")
        if result.routing:
            turn["route"] = {
                "rag": "RAG",
                "data": "Data",
                "both": "Both",
                "clarify": "Clarify",
                "refuse": "Refuse",
            }[result.routing.route]
        if result.status == "refused":
            if (
                classification
                and classification.intent == "unsupported"
                and not (classification.restricted_request)
            ):
                turn.update(
                    result_type="unsupported", route="Unsupported", priority=None, category=None
                )
                return finish(
                    "I can help report store issues and explain supported retail policies."
                )
            turn.update(result_type="refusal", route="Refuse", priority="P1")
            turn["category"] = turn["category"] or "Other or Security"
            turn["escalation"] = escalation(turn["category"], "P1", True)
            turn["guardrails"].update(safety_refusal=True, human_review_required=True)
            return finish(result.answer)
        if result.status == "needs_clarification":
            turn.update(
                result_type="clarification",
                route="Clarify",
                priority=None,
                follow_up_question=result.answer[:2000],
            )
            return finish(result.answer)
        if classification and classification.missing_information and turn["priority"] != "P1":
            question = "Please clarify: " + ", ".join(classification.missing_information)
            if not SafetyAgent().evaluate(PIIAgent().sanitize(question)).allowed:
                return finish("The follow-up could not be validated. Please seek review.")
            turn.update(
                result_type="clarification",
                route="Clarify",
                priority=None,
                follow_up_question=question[:2000],
            )
            return finish(question)
        if not classification or result.status not in {"answered", "partial"}:
            if turn["priority"] == "P1":
                turn["escalation"] = escalation(turn["category"], "P1", True, True)
                turn["guardrails"]["human_review_required"] = True
                turn["recommendations"] = [
                    "Immediately contact Store Manager and the relevant support team."
                ]
                return finish(turn["recommendations"][0] + " " + result.answer)
            return finish(result.answer)
        if (
            classification.category == "POS and Payments"
            and turn["priority"] != "P1"
            and not re.search(r"\b(one|single|all|multiple)\b|entire|store.wide", clean, re.I)
            and classification.intent == "incident"
        ):
            question = "Is one register affected or are all registers down?"
            turn.update(
                result_type="clarification",
                route="Clarify",
                priority=None,
                follow_up_question=question,
            )
            return finish(question)
        catalog = policies()
        if result.rag:
            for cited in result.rag.citations:
                key = cited.filename + "#" + cited.heading_slug
                actual = catalog.get(key)
                if not actual or actual["source_hash"] != cited.source_hash:
                    turn["guardrails"]["human_review_required"] = True
                    turn["limitations"].append("Policy citation is stale or unresolved.")
                    return finish("Supporting policy could not be verified. Please seek review.")
                citation = {
                    k: actual[k] for k in ("section_id", "filename", "heading", "source_hash")
                }
                if citation not in turn["citations"]:
                    turn["citations"].append(citation)
            if result.rag.status == "answered" and turn["citations"]:
                # Keep the graph's grounded statements, with stable public citation identifiers.
                text_steps = re.sub(r"\[[^\]]+\]", "", result.rag.answer)
                turn["recommendations"] = [
                    sanitize(line.strip())[0][:2000]
                    for line in text_steps.splitlines()
                    if line.strip()
                ][:6]
        if result.data:
            for evidence in result.data.evidence:
                record_ids = [
                    str(row.get("sku") or row.get("receipt_id") or row.get("store_id"))[:80]
                    for row in evidence.rows
                    if row.get("sku") or row.get("receipt_id") or row.get("store_id")
                ]
                turn["evidence"].append(
                    dict(
                        source=evidence.query,
                        record_ids=record_ids[:50],
                        summary=sanitize(json.dumps(evidence.rows, ensure_ascii=True))[0][:2000]
                        or "No matching evidence",
                        query_template_id="validated_sql_" + evidence.query,
                    )
                )
        priority, category = turn["priority"], turn["category"]
        priority_source = catalog.get("01_retail_operations_sop.md#priority-rules")
        if priority_source and turn["citations"]:
            turn["citations"].append(
                {
                    key: priority_source[key]
                    for key in ("section_id", "filename", "heading", "source_hash")
                }
            )
        approval = priority == "P1" or category in {
            "Vendor and Supply Chain",
            "Product Quality and Safety",
        }
        review = result.human_review_required
        if category == "Returns and Refunds":
            no_receipt = bool(
                re.search(r"no[ -]receipt|without.*receipt|receipt missing", clean, re.I)
            )
            amounts = re.findall(r"(?:INR|Rs\.?|₹)\s*([\d,]+)", clean, re.I)
            amount = max((int(value.replace(",", "")) for value in amounts), default=0)
            approval = amount >= 5000 or (no_receipt and amount >= 1000)
            review = review or no_receipt or approval
        review = review or approval or classification.confidence < 0.60
        turn["guardrails"]["human_review_required"] = review
        turn["escalation"] = escalation(category, priority, review, approval)
        turn["result_type"] = "recommendation"
        if priority == "P1":
            turn["recommendations"].insert(
                0, "Immediately contact Store Manager and the relevant support team."
            )
        # A fact-only or partially grounded response cannot authorize a validated issue ticket.
        complete = (
            result.status == "answered"
            and turn["citations"]
            and turn["recommendations"]
            and classification.confidence >= 0.60
            and not classification.missing_information
        )
        if (
            complete
            and classification.intent in {"incident", "recommendation"}
            and priority != "P4"
        ):
            revision = conversation.get("draft_revision", 0) + 1
            conversation["draft_revision"] = revision
            turn["ticket_draft"] = dict(
                draft_id=uid(),
                conversation_id=conversation["conversation_id"],
                revision=revision,
                title=f"{category}: {clean[:140]}"[:200],
                description=clean[:4000],
                affected_store_id=store,
                sku=context.get("sku"),
                register_id=context.get("register_id"),
                category=category,
                priority=priority,
                confidence=classification.confidence,
                recommendations=turn["recommendations"],
                citations=turn["citations"],
                evidence=turn["evidence"],
                escalation=turn["escalation"],
                review_required=review,
                approval_required=approval,
                validation_status="validated",
                generation_allowed=True,
                expires_at=(now() + timedelta(minutes=30)).isoformat(),
            )
        return finish(
            (turn["recommendations"][0] + " " if priority == "P1" else "") + result.answer
        )
