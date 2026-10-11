# StorePilot frontend

A simple React interface for the existing FastAPI backend.

## Run

Start the backend on 127.0.0.1:8000, then run `npm install` and `npm run dev` here. Vite proxies `/api` to the backend. Sign in with an employee ID and its exact assigned store ID from the backend directory.

## Screens

- Dashboard: authorized ticket counts, filters, paginated recent tickets, details, and creator-only status updates. Reopening a closed ticket requires a reason.
- Copilot: backend conversations with category and priority first, readable policy steps and database result tables, policy sources, structured SKU context, draft review, and ticket creation. Query sources and preview limits remain visible; incomplete JSON is preserved as text.
- Analytics/Query: natural-language questions about tickets, stock, products, vendors, deliveries,
  returns and policies. LLM-generated SQL runs through the backend tool; actual results appear as
  expandable supporting text with sources and limits, followed by a final LLM explanation of at
  most 20 words. Its filters default to all ticket statuses and dates.

The Dashboard's Live tickets view shows Open cases from the imported snapshot and new application
tickets. All tickets includes other statuses; New tickets only excludes imported cases.
Historical snapshots are read-only and end at noon IST on 10 October 2026. Copilot uses the
guarded LangGraph workflow and policy retrieval. Analytics reads inventory/vendor facts;
operational inventory changes are not implemented.

Sessions are validated with `/api/me` on reload. Private chat remains in memory and is cleared on logout. Messages are displayed from server-sanitized conversation history. Message retries reuse a client UUID; ticket-save retries reuse an idempotency key. The server decides access, classification, and whether a draft can be saved.

For deployment, configure the host to forward `/api` to FastAPI; Vite's proxy applies during development only.

## Verify

`npm run build` and `npm run lint`.

Browser checks: `npm ci --prefix tests`, then `npm --prefix tests test`. See `tests/README.md` for browser and external-server options.

## Docker and verification

Run `docker compose up --build` from the repository root. Open <http://localhost:8081>.
Nginx serves the production build and proxies `/api` to the backend container.

From `tests/`, `npm test` runs eight browser fixture journeys; `npm run test:integration` runs
seven real API/SQLite/graph browser journeys. `npm run typecheck` checks both test configurations.
See [Docker and integration report](../docs/DOCKER_AND_INTEGRATION.md) for setup and limits.
