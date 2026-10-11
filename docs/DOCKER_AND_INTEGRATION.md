# StorePilot — Docker and integration verification

## Run frontend and backend together

From the project root, with Docker Desktop's Linux engine running:

```powershell
docker compose up --build
```

For background operation:

```powershell
docker compose up --build -d --wait
```

- Frontend: <http://localhost:8081>
- FastAPI/Swagger: <http://localhost:8001/docs>
- Same-origin API health: <http://localhost:8081/api/health>

The first build downloads images and locked dependencies. Backend startup then downloads local
embedding weights and builds the 28-section policy index. Subsequent starts reuse persistent cache;
the indexer checks source/configuration hashes and avoids rewriting an unchanged index.

## Configuration and persistence

Compose reads optional `backend/.env` at runtime. The existing `GROQ_API_KEY` enables live model
stages; it is never copied into images or passed to frontend builds. Without a model key,
login/dashboard/guards still work and chat health reports unavailable. If indexing cannot complete,
the backend serves its other operations with degraded readiness and a clear startup log.

Container paths override workstation database/cache paths:

| Resource | Container storage |
| --- | --- |
| Operational source | Host `backend/database/retail.db`, mounted read-only |
| Application records/sessions | Named volume `storepilot_application-data` at `/app/state` |
| Embeddings and Chroma | Named volume `storepilot_rag-cache` at `/app/cache` |
| JWT signing key | Configured `JWT_SECRET`, or generated once in the application volume |

Docker application state is separate from local `backend/database/storepilot.db`; existing local
application tickets are not automatically imported into the new volume. The supplied retail
snapshot is shared. Named volumes preserve container tickets and sessions across recreation.
The backend runs as a non-root user. No separate Chroma service is necessary for the current
embedded persistent client.

Nginx serves the built React app and proxies `/api/` to `backend:8000`. Frontend startup waits for
backend database health; this is different from requiring the optional model provider to be ready.
Only loopback ports are published. Defaults 8081/8001 avoid the existing Apache/Python
services on this workstation at 8080/8000. Set `FRONTEND_PORT` or `BACKEND_PORT` in the shell to change ports.

Useful commands:

```powershell
docker compose config --quiet
docker compose ps
docker compose logs -f
docker compose exec backend python -m app.agents.rag index
docker compose down
```

`down` preserves the named volumes. Removing those volumes removes their application state/cache.
To inspect configuration without displaying provider credentials, use `config --quiet`.

## Checks and findings on 10 October 2026

- Backend: **345 passing tests**, including safety, combined reporting, persistence and store/escalation scope regressions. Ruff passes.
- Existing browser suite: **8 passing tests**, with deterministic HTTP responses.
- New actual-API browser suite: **7 passing tests**, with real FastAPI, authentication, graph,
  policy validation, SQL and temporary SQLite persistence; only model/retrieval adapters are offline.
- Frontend lint, production build and browser TypeScript checks pass.
- A real Groq/Chroma POS request returned grounded, cited troubleshooting advice after fixing a
  false-positive safety match. This checks one live scenario rather than certifying model quality.

The live test found `store-wide POS/payment outage, payment data...` in the Priority Rules policy
was matched as a command to store payment data. Handling verbs now require whitespace or a colon;
unsafe commands still refuse, while the operational adjective `store-wide` remains allowed.

A new browser regression also reproduced a committed ticket whose first HTTP response was lost.
The frontend used to reject its now-disabled draft on retry. Retry now lets the backend replay
with the same idempotency key, returning the committed ticket without a duplicate save.
Dashboard analytics now passes its private thread ID when answering a clarification.

Run the checks:

```powershell
cd backend
uv run pytest -q
uv run ruff check app scripts tests docker
```

```powershell
cd frontend/tests
npm ci
npm test
npm run test:integration
npm run typecheck
```

`test:integration` starts backend on 18000 and Vite on 15173, creates temporary application state,
and cleans it up on server shutdown. It does not alter user application records or the source
snapshot. The normal browser suite uses port 5173. Both use installed Edge by default.

Docker Desktop initially displayed an inference-manager socket startup error. The engine later
responded and image builds proceeded without factory reset, volume deletion or feature disabling.
Both containers built and reported healthy at ports 8081/8001. A live API check through Nginx
verified all health capabilities ready, employee login, 274 authorized historical tickets for
E0001, a cited Copilot recommendation, ticket save, idempotent replay, status updates and model-backed
ticket analytics. Container recreation preserved the same JWT session, closed ticket and ready
retrieval cache; Nginx continued routing to the recreated backend. One closed synthetic ticket
labelled `Docker smoke check` remains in the separate Docker application database.
An Edge check against the built Docker frontend passed login, historical dashboard, Copilot
navigation and logout without browser page errors.

The latest frontend defaults to Live tickets (Open), with existing plus new records and All time.
Rebuilding and recreating the containers preserved the existing application ticket. A deployed
level-2 employee sees 121 authorized Open cases, and foreign-store reporting requests return 403.
See [database and ticket visibility checks](DATABASE_AND_TICKET_VISIBILITY.md) for storage locations
and the distinction between reporting-store permission and escalation-based ticket reads.

## Implementation references

- [uv's Docker integration](https://docs.astral.sh/uv/guides/integration/docker/)
- [Compose service health and startup ordering](https://docs.docker.com/compose/how-tos/startup-order/)


## Broader analytics verification

See [LLM → SQL tool → frontend analytics](ANALYTICS_WORKFLOW.md). The final backend suite
passes 345 tests, and the browser suites pass 8 fixture plus 7 actual-API journeys. The rebuilt
production Docker UI also passed a real LLM-generated SQL question for the most frequent issue
in ST004, showing actual results as readable text with no browser errors. Persistent application
and RAG volumes were retained through recreation. Repeated live checks encountered a provider
rate limit; a later production browser request succeeded.
