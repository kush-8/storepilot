# StorePilot — Product Requirements Document

Version: 2.0 | Date: 10 October 2026 | Status: proposed scope; implementation paused

## 1. Product goal

StorePilot is an employee workspace for reporting retail issues, receiving grounded next steps, creating persistent tickets, and investigating the tickets the employee is allowed to see. Punjab Sports Mart is the supplied retailer and dataset context; StorePilot is the application name.

Two main pages: **Dashboard** and **Copilot**. Dashboard combines the previous overview and analytics experiences. Copilot is a conversational issue-reporting and ticket-generation experience. Evaluation is a backend test workflow with no frontend page, navigation item, or public evaluation API.

The agreed stack remains React/TypeScript/Vite, Python/uv/FastAPI, LangGraph, Chroma, SQLite, and Docker Compose. Existing code is a starter scaffold. This document specifies future behaviour; it does not claim that agents, authentication, ticket storage, or product screens exist.

## 2. Users and access

Employees report problems relevant to their work; managers and other employees inspect permitted tickets and ask dashboard questions. The backend obtains the viewer's employee ID from verified server-controlled identity and looks up the current level in employee_master.

Confirmed ticket visibility rule:

`ticket creator's current escalation_level <= viewer's current escalation_level`

| Viewer level | Visible creator levels |
| --- | --- |
| 1 | 1 |
| 2 | 1, 2 |
| 3 | 1, 2, 3 |
| 4 | 1, 2, 3, 4 |

Use the existing numeric levels as requested, even where role names do not imply this ordering. A Regional Manager at level 2 cannot see a Store Manager's level-4 tickets. Priority P1–P4 is independent of employee level.

Apply this rule to lists, details, searches, counts, charts, drill-downs, related-ticket evidence, and analytics before aggregation or model context. A store filter can narrow the result; it cannot widen access. No automatic extra store restriction is specified. Missing identity or employee level fails closed.

Visibility does not grant refund approval, external workflow authority, or access to another employee's private chatbot conversation. Requested prototype login: enter Employee ID and assigned Store ID; the backend validates the pair and issues a signed JWT. No login implementation is authorized yet. These identifiers establish directory context but are not secret credentials.

## 3. Required capabilities

| ID | Capability | Acceptance |
| --- | --- | --- |
| SP-01 | Combined dashboard | Visible ticket metrics, filters, ticket list/detail, and an integrated Ask StorePilot analytics panel on one page |
| SP-02 | Chat copilot | Multi-turn issue reporting with conversational follow-ups and retained sanitized context |
| SP-03 | Guardrails first | Every new turn passes PII masking then safety checks before the router and specialist agents |
| SP-04 | Explicit router | Typed decision: RAG, Data, Both, clarification, dashboard redirect, or refusal/unsupported |
| SP-05 | Grounded guidance | Show recommended steps, policy citations, relevant data evidence, category, priority, and concise uncertainty |
| SP-06 | Ticket generation | Prepare a server-held draft; Generate ticket persists a validated ticket and returns its real application ticket ID |
| SP-07 | Durable tickets | SQLite stores sanitized ticket fields, recommendations, citations/evidence, routing, lifecycle events, and conversation linkage |
| SP-08 | Level-based visibility | Enforced in backend repositories and every ticket-derived analytics path, including direct-ID access |
| SP-09 | Dashboard analytics agent | Answer supported questions using authorized ticket SQL and relevant source-data lookups; retain filters/window/provenance |
| SP-10 | Human escalation | P1, confidence below 0.60, policy conflict, suspicious requests, and approval-required situations get appropriate human review |
| SP-11 | Backend evaluation | Evaluate retrieval/grounding and end-to-end guardrail/router/data behaviour without a frontend evaluation feature |

Ticket creation is core functionality, not an optional simulated JSON export. Tickets are real records in the local StorePilot database. External POS actions, refunds, stock transfers, claim submission, and notifications remain unintegrated and must not be claimed as completed.

## 4. Main journeys

### Report an issue and generate a ticket

1. Employee opens Copilot and describes the issue in a chat message.
2. Backend sanitizes the turn, checks safety, and routes it.
3. If impact, location, or another essential detail is unclear, Copilot asks a focused question.
4. RAG retrieves policy; Data queries relevant inventory, receipts, vendors, or permitted tickets; Both combines them.
5. Copilot gives recommended steps and a concise explanation with evidence.
6. A ticket draft appears in the chat with classification, affected location/product/register, route, and review flags.
7. Employee selects Generate ticket. The backend validates and saves it atomically.
8. Chat shows the ticket ID and View ticket; the dashboard refreshes.

Ticket generation records the report; it does not approve the underlying operational action. Urgent safety guidance must be shown immediately, even while optional facts remain unknown. P1 drafts can proceed with minimal confirmed information and explicit unknowns.

### Investigate from the dashboard

Employee reviews visible workload, filters tickets, opens a detail panel, or asks the dashboard analytics agent a question. The agent uses the same authorized ticket scope as the cards and list. An analytics question does not create an incident ticket automatically.

## 5. Categories and priority

Eight operational categories: POS and Payments; Inventory and Replenishment; Pricing and Promotions; Returns and Refunds; Vendor and Supply Chain; Product Quality and Safety; Customer Service; Other or Security.

| Priority | Meaning |
| --- | --- |
| P1 | Immediate human escalation: store-wide payment failure, injury/unsafe equipment, suspicious restricted-data request |
| P2 | High-impact operational issue without immediate danger |
| P3 | Routine operational issue |
| P4 | General inquiry/reporting request |

Apply supplied policies and escalation routes rather than blindly copying historical labels. Distinguish payment degradation from inability to process payments; show a policy conflict when ambiguity remains.

No-receipt returns require manager review. Refunds >= INR 5,000 and no-receipt refunds >= INR 1,000 require approval. Employee visibility levels do not establish approval authority.

## 6. Data, persistence, and time

Preserve the nine CSV tables in read-only retail.db. Add a separate writable storepilot.db for tickets, conversations, drafts, and audit events; see TICKET_DATA_MODEL.md. Rebuilding the source snapshot must not erase application tickets.

Historical support cases may be imported once into tickets with source IDs and recorded-label provenance. Original files remain immutable. Evaluation expected answers never enter Chroma or operational evidence.

Historical challenge queries and backend evaluation use 2026-10-10T12:00:00+05:30 and rolling intervals (start, end]. Live application tickets use actual server timestamps and a captured server-now query endpoint; never exclude new tickets merely because they are later than the challenge anchor. Every analytics result identifies its dataset mode and time window.

## 7. Success and deliverables

- Updated product, flow, stack, engineering, system, frontend, and ticket-data documents.
- Independent React/Vite frontend and uv/FastAPI backend with reproducible lockfiles.
- Dashboard and chat Copilot with follow-up, recommendation, ticket-save, and detail flows.
- Compiled LangGraph workflow with PII, Safety, Router, RAG, Data, Analytics, and validated response/ticket handoffs.
- Reproducible Chroma policy indexing with resolvable citations.
- Durable SQLite application database and migrations, source-preserving import, safe historical ticket seeding.
- Backend visibility tests, ticket lifecycle/idempotency tests, RAG/pipeline evaluation outputs, and frontend build/UI checks.
- Dockerfiles/Compose with read-only source mounts and separate persistent application/vector stores.

Retain challenge targets: category/priority accuracy >=75%, citation presence >=85%, safety checks 100%, and data-use correctness >=75%. Report retrieval relevance and citation support separately; do not fabricate results before inference.

## 8. Scope boundaries and current status

No frontend evaluation or separate Analytics/Overview page. No execution of refunds, transfers, claims, or external notifications. No model-generated arbitrary SQL or direct model writes to tickets. Employee ID + Store ID/JWT login is specified in REQUIREMENTS.md and API_CONTRACT.md; implementation remains paused.

Current starter endpoints and imported data do not yet enforce the new employee visibility rule. Do not expose the unscoped starter dashboard as the proposed finished employee dashboard.
