# StorePilot browser TDD tests

This isolated Playwright package leaves the frontend application manifest unchanged. The tests drive the existing Vite app in Edge with deterministic HTTP fixtures; they require no model key or running backend. `api-fixture.ts` is test-only scripted HTTP data, not application implementation.

## Run

From `frontend/` install existing app dependencies without creating an app lockfile:

```powershell
npm install --package-lock=false --cache tests/.cache/npm-app
cd tests
npm ci --cache .cache/npm
npm run test:list
npm run typecheck
npm test
```

Playwright starts Vite at http://127.0.0.1:5173 and stops it after the run. Edge is the default installed browser on this machine. For another browser installation set STOREPILOT_BROWSER_CHANNEL, or use `chromium` and install that Playwright browser with `npx playwright install chromium`. To use an already-running frontend set STOREPILOT_URL. Browser/server startup may require execution outside the Windows sandbox.

The checked-in lockfile belongs to this test package only. Cache, node_modules, traces and test-results are ignored. Retry count is zero so failures remain visible.

## Every browser test

| Journey | Actions | Required result |
| --- | --- | --- |
| Dashboard and Copilot navigation | Log in; inspect brand, scope and navigation | StorePilot brand; Analytics question box within Dashboard; no Overview/Analytics/Evaluation destinations; protected requests send bearer token |
| Follow-up → recommendation → save | Report ambiguous reader issue; answer all-register impact; inspect steps; Generate ticket; return to Dashboard | Clarification precedes draft, escalation step visible, one save, committed receipt ID and ticket row |
| Failed save and retry | Make first save return 503; click Retry | No premature receipt, draft retained, second attempt reuses the same nonempty idempotency key |
| Dashboard Analytics | Ask for unresolved tickets by store | Grounded table/answer visible; zero ticket-generation requests |
| Logout privacy | Start a private chat; log out | Login controls restored, previous message removed, fixture bearer token absent from local/session storage |
| Mobile and keyboard | Set viewport to 360×800; log in; focus chat composer | Accessible labelled controls, visible focused composer and no horizontal overflow |

The UI selectors establish accessible names: Employee ID, Store ID, Dashboard, Copilot, Message, Send and Generate ticket. Each browser test uses a fresh HTTP fixture/session. Real API tests in backend/tests prove storage and scope independently; these UI journeys prove client behaviour with known responses.

## Recorded red baseline

All **6 tests collected and executed; 6 failed, 0 skipped** against the starter Vite scaffold. Each reached the page but timed out waiting for the Employee ID login control, which has not been implemented. Edge and Vite launched successfully; no browser startup errors occurred. The baseline used a 6-second test timeout (`npm test -- --timeout=6000`); normal configured timeout is 20 seconds. Passing test collection is not a passing journey.

The current first failure blocks deeper UI assertions until login is implemented. Follow-up/save/retry/logout assertions will be exercised progressively during TDD. No frontend product code was changed to make these tests pass.

See [full app/API flow](../../backend/tests/API_FLOW_AND_TESTS.md) and [backend test guide](../../backend/tests/README.md).
