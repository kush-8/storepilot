# StorePilot frontend

A simple React interface for the existing FastAPI backend. All changes are confined to this frontend directory.

## Run

Start the backend on 127.0.0.1:8000, then run `npm install` and `npm run dev` here. Vite proxies `/api` to the backend. Sign in with an employee ID and its exact assigned store ID from the backend directory.

## Screens

- Dashboard: authorized ticket counts, filters, recent tickets, and ticket-count questions.
- Copilot: backend conversations, policy sources, structured SKU context, draft review, and ticket creation.
- Tickets: paginated tickets, details, and creator-only status updates. Reopening a closed ticket requires a reason.

Live data includes application tickets only. Historical snapshots are read-only and end at noon IST on 10 October 2026. The current backend Copilot uses local rules and policy retrieval. Inventory management, vendor metrics, and standalone agent workflows have no connected API and are omitted from navigation.

Sessions are validated with `/api/me` on reload. Private chat remains in memory and is cleared on logout. Messages are displayed from server-sanitized conversation history. Message retries reuse a client UUID; ticket-save retries reuse an idempotency key. The server decides access, classification, and whether a draft can be saved.

For deployment, configure the host to forward `/api` to FastAPI; Vite's proxy applies during development only.

## Verify

`npm run build` and `npm run lint`.

Browser checks: `npm ci --prefix tests`, then `npm --prefix tests test`. See `tests/README.md` for browser and external-server options.
