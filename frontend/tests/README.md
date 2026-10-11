# StorePilot browser TDD tests

This isolated Playwright package leaves the frontend application manifest unchanged. The tests drive the existing Vite app in Edge with deterministic HTTP fixtures; they require no model key or running backend. `api-fixture.ts` is test-only scripted HTTP data, not application implementation.

## Run

From `frontend/`, install application dependencies from its checked-in lockfile:

```powershell
npm ci --cache tests/.cache/npm-app
cd tests
npm ci --cache .cache/npm
npm run test:list
npm run typecheck
npm test
```

Playwright starts Vite at http://127.0.0.1:5173 and stops it after the run. Edge is the default installed browser on this machine. For another browser installation set STOREPILOT_BROWSER_CHANNEL, or use `chromium` and install that Playwright browser with `npx playwright install chromium`. To use an already-running frontend set STOREPILOT_URL. Browser/server startup may require execution outside the Windows sandbox.

The browser package has its own lockfile, separate from the frontend application lockfile. Cache, node_modules, traces and test-results are ignored. Retry count is zero so failures remain visible.

## Every browser test

| Journey | Actions | Required result |
| --- | --- | --- |
| Dashboard, Copilot and Analytics/Query navigation | Log in; inspect brand, scope and navigation; open Analytics/Query | Three tabs; ticket overview on Dashboard; query box only on Analytics/Query; no Tickets destination; protected requests send bearer token |
| Follow-up → recommendation → save | Report ambiguous reader issue; answer all-register impact; inspect steps; Generate ticket; return to Dashboard | Clarification precedes draft, escalation step visible, one save, committed receipt ID and ticket row |
| Failed save and retry | Make first save return 503; click Retry | No premature receipt, draft retained, second attempt reuses the same nonempty idempotency key |
| Analytics/Query | Select filters; ask for unresolved tickets by store; change filters | Selected filters sent; grounded table/answer visible; stale results cleared; zero ticket-generation requests |
| Logout privacy | Start a private chat; log out | Login controls restored, previous message removed, fixture bearer token absent from local/session storage |
| Mobile and keyboard | Set viewport to 360×800; log in; focus chat composer | Accessible labelled controls, visible focused composer and no horizontal overflow |
| Structured Copilot response | Ask for inventory; inspect classification, policy steps, rows and preview limits; send a follow-up | Category and priority precede guidance, JSON becomes tables, zero/null remain distinct, classification survives follow-up |
| Query parsing on mobile | Return fenced/nested JSON, empty results and incomplete JSON at 360×800 | Values remain safe text, nested data is readable, empty results are explicit, incomplete data stays visible, no page overflow |

The UI selectors establish accessible names: Employee ID, Store ID, Dashboard, Copilot, Message, Send and Generate ticket. Each browser test uses a fresh HTTP fixture/session. Real API tests in backend/tests prove storage and scope independently; these UI journeys prove client behaviour with known responses.

## Current verification

All eight fixture-based browser journeys pass against the integrated frontend. The previous red
baseline predates the current login/screens and no longer represents the application.

Run the actual React-to-FastAPI integration suite:

```powershell
npm run test:integration
npm run typecheck
```

Its seven tests cover private clarification/citations, ticket save/dashboard/analytics/status/logout,
historical data and PII refusal, replay after a committed ticket's HTTP reply is lost, and private
analytics clarification threads, existing Open-case visibility and persistence after reload/status changes,
assigned-store reporting with a recoverable cross-store clarification, and broad SQL analytics
shown as readable result text. The fixture starts a real backend at port 18000 and Vite at 15173,
with a temporary application database. The graph, JWT, SQL and storage are real; model adapters and
retrieval are deterministic. It needs the backend virtual environment installed first.

See [Docker/integration results](../../docs/DOCKER_AND_INTEGRATION.md),
[full app/API flow](../../docs/COPILOT_WORKFLOW_AND_TESTS.md) and
[backend test guide](../../backend/tests/README.md).
