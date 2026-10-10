# StorePilot frontend

React with Vite, plain CSS, Lucide icons and Recharts. The current application uses JavaScript/JSX.
Login calls the backend with a demo fallback; Copilot, dashboard and other demo views still use
local mock data. Connecting these views to the verified backend remains outstanding.

```powershell
npm ci
npm run dev
npm run lint
npm run build
```

Vite runs on port 5173 and proxies `/api` to the FastAPI server at `127.0.0.1:8000`.
Keep API credentials and database files in the backend. The npm lockfile is checked in;
unused Vite starter assets and a duplicate lockfile backup have been removed.

See the [frontend design](../docs/FRONTEND_DESIGN.md),
[API/workflow report](../docs/COPILOT_WORKFLOW_AND_TESTS.md) and
[browser test plan](tests/README.md). Passing lint/build does not prove backend-connected UI journeys.
