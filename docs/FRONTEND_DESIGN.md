# StorePilot — Frontend Design

Version: 2.0 | React + TypeScript + Vite | Status: design only

## 1. Experience and branding

App name: **StorePilot**. Subtitle: **Retail issues, guided and tracked**. Punjab Sports Mart appears as retailer context where useful, not the application name.

Two navigation items: Dashboard and Copilot. Dashboard combines ticket overview and analytics. Copilot is a chatbot dedicated to issue reporting and ticket generation. Evaluation is backend-only: no employee screen, navigation entry, evaluation widgets, or judge inspector in the frontend.

Frontend displays validated safe results from FastAPI. Agent graph, SQL, model credentials, Chroma internals, and evaluation files remain backend concerns.

## 2. Visual direction

Calm retail workspace: light surfaces, dark ink, restrained green accents, clear priority labels, and compact readable data. Use system fonts.

| Token | Light value | Purpose |
| --- | --- | --- |
| Canvas | #F5F7F4 | Workspace background |
| Surface | #FFFFFF | Cards/chat/detail panels |
| Primary ink | #15251D | Main text |
| Secondary ink | #526057 | Supporting text |
| Brand | #176B49 | Actions/selected navigation |
| Border | #DCE4DD | Separators |
| Critical | #B42318 | P1/safety |
| Warning | #8A4B08 | P2/review |

Provide theme-aware equivalents for dark mode. Priority always has a text label. Use 4/8/12/16/24/32 px spacing, 12 px panel corners, 8 px controls, 16 px body text and 14 px supporting text. Verify contrast during implementation.

## 3. Application shell

Desktop: compact sidebar, flexible content, header with employee identity, role, and read-only escalation level. Mobile: brand/profile header and two accessible navigation controls; stack content.

Show a scope label: **Tickets from employees at your level or below**. Do not imply a managerial hierarchy based on role names. Profile level comes from backend identity, not a user-editable authorization setting.

Before the two-page workspace, a login view collects Employee ID and assigned Store ID. Backend validates the pair and issues JWT. Keep the token in memory, clear private data on logout/expiry, and return to login. No password field is requested. Login and JWT remain unimplemented.

## 4. Dashboard: overview and analytics together

```text
StorePilot                 Employee / role / level
Dashboard | Copilot

Dashboard             Time window / store / priority / status
Tickets from your level or below

Open tickets       P1 urgent       P2 review       Resolved
Priority/category distributions and trend (when data supports it)

Tickets                                      Ask StorePilot
ID / issue / priority / status / store        Analytics question
Click a row -> ticket detail                  Answer + evidence/table
                                              Suggested follow-up
```

Cards, distributions, table, and analytics share the same backend authorization and filter context. Counts must not be chain-wide totals if the employee cannot see the underlying tickets. Operational inventory/receipt evidence is labelled separately from ticket workload.

Default data mode uses live application tickets. Historical replay is an explicit source/time option and displays the fixed anchor. Never label static inventory snapshots as real-time telemetry.

The Ask StorePilot panel is embedded in the dashboard, expanded or docked alongside the ticket list on desktop and stacked below it on mobile. Examples: “Open high-priority tickets by store”, “Which issue categories are recurring?”, “Why is this SKU unavailable?” Responses show short findings, requested window, authorized result table/chart, evidence and limitations. Selecting a result narrows the ticket list or opens permitted detail.

## 5. Chat Copilot

One main conversation column with an optional desktop ticket-draft side panel. On mobile, the draft is an inline chat card. The composer stays at the end of the conversation rather than a separate left-hand issue form.

Empty state: **What happened in your store?** Offer concise issue examples. Employee/store session context is prefilled; affected store/SKU/register details can be added or asked conversationally.

Turn types:

- Employee message, rendered as text and sanitized by the backend.
- Copilot follow-up question with optional quick replies: one register / several / all.
- Grounded recommendation with category/priority, concise explanation, ordered steps, policy citations and data evidence.
- Human-review/safety guidance where required.
- Ticket draft with editable safe issue facts and Generate ticket action.
- Ticket receipt with saved ticket ID and View ticket.

Do not show agent names or graph mechanics to employees. During processing use “Checking the issue…” or “Preparing recommended steps…”. Show uncertainty as plain language; any numeric confidence is labelled an estimate. Do not show hidden chain-of-thought.

Example:
Employee: “Card reader stopped working.”
Copilot: “Is one register affected, or are all registers unable to process card payments?”
Employee: “All registers at ST003.”
Copilot: P1 guidance, ordered immediate steps, POS runbook citation, Store Manager + POS Support route, then outage-ticket draft.

Follow-ups are normal chat turns and always pass guardrails again. Do not ask for card numbers, credentials, or unnecessary customer details.

## 6. Ticket draft and saved detail

Draft summary: title, affected location, optional SKU/register, category, priority, known impact, recommended steps, evidence, routing team, approval/review flags. Creator identity and classification are server-controlled. Editing substantive issue facts triggers reanalysis.

Primary action: **Generate ticket**. During save: **Saving ticket…**, with repeat submission disabled. Show **Ticket created: [ID]** only after the database transaction commits. Retry uses the same idempotency key. A local application ticket is persisted; external teams have not been notified merely because a ticket exists.

Ticket detail drawer shows saved report, priority/status, creator ID/level where relevant, recommendations, policy/data evidence, escalation route, and lifecycle history. It does not show the creator's whole private chat. MVP readers inspect tickets; write permissions beyond creator ticket creation require an explicit backend policy.

## 7. States and accessibility

| State | UI |
| --- | --- |
| Unclear query | A focused question in chat; retain sanitized context |
| P1 risk | Prominent urgent guidance/route before optional questions |
| Refusal | Brief safe response; no restricted content/evidence |
| Low confidence/conflict | Explain uncertainty and human review |
| Draft incomplete | Explain the specific missing essential detail |
| Save failed | Preserve draft and Retry; no success badge |
| Hidden/nonexistent ticket | Generic not-found message |
| No visible tickets | Empty state with filters and Report an issue |
| Model unavailable | Dashboard SQL still usable; chat capability clearly unavailable |
| Analytics loading/error | Scoped loading indicator or safe Retry |

Keyboard-accessible navigation and controls, visible labels/focus, 44 px touch targets, text priority labels, accessible chart/table equivalents, and layouts down to 360 px. Wrap citations and IDs. Focus follows submitted responses/created-ticket receipt without repeatedly announcing the full chat; use polite live updates and urgent alerts appropriately.

## 8. Components and frontend data

AppShell, EmployeeContext, DashboardFilters, ScopedMetricCard, TicketTable, TicketDetailDrawer, DashboardAnalyticsPanel, ChatThread, ChatMessage, FollowUpQuestion, RecommendationCard, CitationList, EvidenceTable, EscalationPanel, TicketDraftCard, TicketReceipt, StatusPanel.

Shared API types/client outside screens. Fetch cancellation and explicit stale-response handling prevent identity/filter changes from showing a previous employee's data. Clear ticket/analytics caches and open detail on session changes. No raw messages in localStorage; conversation history is sanitized and server-owned.

Render text without dangerouslySetInnerHTML. Citation links resolve through a trusted catalog. No secrets or database authority in frontend environment variables.

## 9. Implementation sequence after review

1. Requested Employee ID + Store ID/JWT identity boundary, two-page shell, scoped dashboard/ticket APIs.
2. Chat thread/composer, guardrail-driven follow-ups, grounded recommendation rendering.
3. Server draft, persistent Generate ticket, saved detail and dashboard refresh.
4. Embedded analytics panel with scoped results and drill-down.
5. Accessibility, mobile/error-state checks, deployment packaging.

No frontend evaluation work is planned.
