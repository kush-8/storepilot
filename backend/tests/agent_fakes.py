"""Offline structured models; production graph, RAG validation and SQL tools stay real."""

import json
import re
from datetime import datetime
from types import SimpleNamespace

from langchain_core.runnables import RunnableLambda

from app.agents.data.agent import DataAgent
from app.agents.data.sql_tool import ReadOnlySqlExecutor
from app.agents.rag.config import BACKEND_ROOT
from app.agents.rag.generation.chain import build_answer_chain
from app.agents.rag.ingestion import load_policy_documents
from app.agents.rag.service import RagAgent
from app.agents.router.agent import RouterAgent
from app.agents.triage.agent import TriageAgent
from app.agents.workflow.nodes import WorkflowNodes
from app.agents.workflow.service import RetailWorkflow


def offline_workflow(database):
    calls = []

    def tracked(stage, function):
        def invoke(prompt):
            text = prompt.to_messages()[-1].content
            calls.append((stage, text))
            return function(text)

        return RunnableLambda(invoke)

    def triage(text):
        category = "POS and Payments"
        if re.search(r"stock|inventory", text, re.I):
            category = "Inventory and Replenishment"
        elif re.search(r"pric|shelf", text, re.I):
            category = "Pricing and Promotions"
        elif re.search(r"refund|return", text, re.I):
            category = "Returns and Refunds"
        elif re.search(r"injur|unsafe|handlebar", text, re.I):
            category = "Product Quality and Safety"
        store = re.search(r"\b(?:ST|WH)\d{3}\b", text)
        sku = re.search(r"\bSKU\d+\b", text)
        return dict(
            summary=text[:1000],
            intent="incident",
            category=category,
            priority="P3",
            confidence=0.9,
            entities=dict(
                store_id=store.group() if store else None, sku=sku.group() if sku else None
            ),
        )

    def route(text):
        data = "Inventory and Replenishment" in text
        return dict(
            route="both" if data else "rag",
            reason="Need grounded policy and facts",
            queries=["inventory"] if data else [],
        )

    def retrieve(question):
        docs = load_policy_documents(BACKEND_ROOT / "knowledge_base")
        heading = (
            "Inventory Discrepancy"
            if "Inventory" in question or "stock" in question
            else "Pricing and Promotions"
            if "price" in question.lower()
            else "Returns and Refunds"
            if "refund" in question.lower()
            else "Recall and Safety"
            if re.search(r"injur|unsafe|handlebar", question, re.I)
            else "POS Card Reader Runbook"
        )
        selected = [doc for doc in docs if doc.metadata["heading"] == heading][:2]
        for doc in selected:
            doc.metadata["distance"] = 0.1
        return selected

    def answer(text):
        context = json.loads(text.split("Policy sections (JSON): ")[1])
        return dict(
            insufficient_evidence=False,
            statements=[
                dict(
                    text="Confirm impact and follow the approved procedure; contact support "
                    "with the store, affected equipment and start time.",
                    citation_ids=[context[0]["section_id"]],
                )
            ],
        )

    def sql(text):
        entities = json.loads(text.split("Entities JSON: ")[1].splitlines()[0])
        return {
            "queries": [
                {
                    "evidence_type": "inventory",
                    "sql": "SELECT i.store_id, i.sku, i.on_hand, i.system_qty, p.high_demand "
                    "FROM inventory i JOIN product_master p ON p.sku=i.sku "
                    "WHERE i.store_id=:store_id"
                    + (" AND i.sku=:sku" if entities.get("sku") else "")
                    + " ORDER BY i.sku",
                }
            ]
        }

    def analytics(text):
        group = (
            "affected_store_id"
            if "store" in text.lower()
            else "category"
            if "category" in text.lower()
            else "priority"
        )
        return dict(
            intent="ticket_counts",
            group_by=group,
            status="Open" if "open" in text.lower() else None,
        )

    nodes = WorkflowNodes(
        TriageAgent(tracked("triage", triage)),
        RouterAgent(tracked("router", route)),
        RagAgent(RunnableLambda(retrieve), build_answer_chain(tracked("rag", answer))),
        DataAgent(
            tracked("sql", sql),
            ReadOnlySqlExecutor(database),
            datetime.fromisoformat("2026-10-10T12:00:00+05:30"),
            analytics_model=tracked("analytics", analytics),
        ),
    )
    return SimpleNamespace(workflow=RetailWorkflow(nodes), nodes=nodes, calls=calls)
