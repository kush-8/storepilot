# StorePilot database and ticket visibility check

Verified on 10 October 2026.

## Why existing open tickets were missing

The dashboard originally selected `data_mode=live` and `window=last7d`. That mode reads only
generated tickets from application storage, excluding the imported `support_cases` table.
The date window also excludes older open issues. This was a reporting/filter problem.

The default frontend view is now **Live tickets (Open)** with **All time**. It requests
`data_mode=combined`, `status=Open`, `window=all`, including authorized existing cases and new
tickets. All tickets clears the status restriction; New tickets only selects application records;
Historical snapshot selects imported cases. Selecting another status leaves the Live/Open view.
Lists, dashboard metrics and analytics share the same backend filters and visibility function.

Imported cases retain the historical cutoff of 10 October 2026, noon IST, even in combined mode.
The source contains 550 cases, including 357 marked Open, but later snapshot timestamps and
higher-level creators are excluded. For E0001 at level 2, the deployed default view returns
**121 authorized open cases**. Imported cases remain read-only; new ticket status changes are
creator-only and use a version check.

## How storage actually works

| Store | Contents | Writes |
| --- | --- | --- |
| `backend/database/retail.db` | Nine operational tables, 2,970 rows, source manifest and reporting views | Read-only at runtime |
| Local `backend/database/storepilot.db` | Sessions, JSON conversation/draft/ticket/analytics records, retry receipts and turns | Local backend |
| Docker `storepilot_application-data` volume | Application database and persistent JWT signing key | Docker backend |

`app/models.py` defines validated API inputs. The application uses SQLite directly rather than
an ORM; generated tickets are JSON records in `records` where `kind='ticket'`. They are not inserted
into the immutable source `support_cases` table. Dashboard analytics receives authorized records
and aggregates them; private ticket text does not reach its planning model.

Both local databases passed SQLite integrity checks. Source foreign keys, table counts and import
provenance passed verification. The local application database contains one Open ticket; Docker
contains a separate closed synthetic smoke-test ticket. These are separate environments, so
switching between them does not transfer generated tickets. Neither database was replaced or merged.

The saved Docker ticket survived image rebuild and forced container recreation. Earlier live checks
also verified the same session and signing key remained usable across recreation. Named volumes
survive `docker compose down`; deleting the application volume removes its saved data.

## Store and escalation authorization

- Employees report issues only for their current assigned store, including employees at level 4.
- The reporting store is read-only in the UI and derived from the employee directory on the backend.
- Foreign-store conversation/context/draft requests return 403. Draft store is checked again at save.
- Another store ID in chat asks for clarification without creating a draft. Corrected follow-ups can
  continue without carrying the rejected store request into the model's issue history.
- Ticket reads use `creator.current_level <= viewer.current_level` across stores. Reporting permission
  is distinct from read permission; changing store filters does not grant access to higher-level tickets.
- Levels come from current employee rows, rather than browser inputs, JWT role/level claims or cached
  ticket values. Inaccessible detail IDs return 404. Directory changes take effect on later requests.

## Regression coverage

- Combined Open-case reporting for all four viewer levels: lists, pagination, counts and analytics agree.
- Changing a viewer/creator level refreshes combined list/detail/dashboard/analytics visibility.
- A new application client reads the saved ticket and replays its existing retry receipt.
- Store-scope tests reject cross-store conversations at every level, warehouse bypasses, changed
  message context, legacy foreign-store conversations and foreign-store drafts at commit.
- Browser tests verify existing Open cases, persistence after reload, closing a generated ticket removes
  it from Live tickets, All tickets still shows it, and Copilot locks the reporting store.

See [workflow and endpoint tests](COPILOT_WORKFLOW_AND_TESTS.md) and
[Docker integration results](DOCKER_AND_INTEGRATION.md) for commands and broader verification.
