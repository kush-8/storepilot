-- Test data only: the approved logical schema for isolated API fixtures.
-- This is not an application migration and is never applied to project databases.
PRAGMA foreign_keys = ON;
CREATE TABLE auth_sessions (
 jti_hash TEXT PRIMARY KEY, employee_id TEXT NOT NULL, assigned_store_id TEXT NOT NULL,
 issued_at_utc TEXT NOT NULL, expires_at_utc TEXT NOT NULL, revoked_at_utc TEXT
);
CREATE TABLE conversations (
 conversation_id TEXT PRIMARY KEY, owner_employee_id TEXT NOT NULL, affected_store_id TEXT,
 created_at_utc TEXT NOT NULL, updated_at_utc TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE conversation_messages (
 message_id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations,
 client_message_id TEXT, turn_sequence INTEGER NOT NULL, role TEXT NOT NULL,
 sanitized_content TEXT NOT NULL, pii_checked INTEGER NOT NULL, safety_status TEXT NOT NULL,
 created_at_utc TEXT NOT NULL, UNIQUE(conversation_id, turn_sequence),
 UNIQUE(conversation_id, client_message_id)
);
CREATE TABLE ticket_drafts (
 draft_id TEXT NOT NULL, conversation_id TEXT NOT NULL REFERENCES conversations,
 owner_employee_id TEXT NOT NULL, revision INTEGER NOT NULL, sanitized_payload_json TEXT NOT NULL,
 validation_status TEXT NOT NULL, source_version TEXT NOT NULL, access_version TEXT NOT NULL,
 created_at_utc TEXT NOT NULL, expires_at_utc TEXT NOT NULL, PRIMARY KEY(draft_id, revision)
);
CREATE TABLE tickets (
 ticket_id TEXT PRIMARY KEY, conversation_id TEXT REFERENCES conversations, draft_id TEXT,
 draft_revision INTEGER, created_by_employee_id TEXT NOT NULL, creator_level_at_creation INTEGER,
 creator_role_at_creation TEXT, store_id TEXT NOT NULL, sku TEXT, register_id TEXT,
 title TEXT NOT NULL, description TEXT NOT NULL, category TEXT NOT NULL,
 priority TEXT NOT NULL CHECK(priority IN ('P1','P2','P3','P4')),
 priority_provenance TEXT NOT NULL, confidence REAL,
 status TEXT NOT NULL CHECK(status IN ('Open','In Progress','Closed')),
 impact_summary TEXT, escalation_team TEXT, escalation_channel TEXT, sla_minutes INTEGER,
 review_required INTEGER NOT NULL, approval_required INTEGER NOT NULL,
 approval_status TEXT NOT NULL, origin TEXT NOT NULL, source_case_id TEXT UNIQUE,
 policy_validation_status TEXT NOT NULL, created_at_utc TEXT NOT NULL, updated_at_utc TEXT NOT NULL,
 closed_at_utc TEXT, version INTEGER NOT NULL DEFAULT 1,
 UNIQUE(draft_id, draft_revision)
);
CREATE TABLE ticket_steps (
 ticket_id TEXT NOT NULL REFERENCES tickets, step_order INTEGER NOT NULL,
 sanitized_instruction TEXT NOT NULL, PRIMARY KEY(ticket_id, step_order)
);
CREATE TABLE ticket_citations (
 ticket_id TEXT NOT NULL REFERENCES tickets, section_id TEXT NOT NULL,
 filename TEXT NOT NULL, heading_slug TEXT NOT NULL, source_hash TEXT NOT NULL,
 PRIMARY KEY(ticket_id, section_id)
);
CREATE TABLE ticket_evidence (
 evidence_id TEXT PRIMARY KEY, ticket_id TEXT NOT NULL REFERENCES tickets,
 source_table TEXT NOT NULL, source_record_id TEXT, query_template_id TEXT,
 sanitized_summary_json TEXT NOT NULL, source_hash TEXT, observed_at_utc TEXT NOT NULL
);
CREATE TABLE ticket_events (
 event_id TEXT PRIMARY KEY, ticket_id TEXT NOT NULL REFERENCES tickets,
 actor_employee_id TEXT NOT NULL, event_type TEXT NOT NULL, old_status TEXT, new_status TEXT,
 sanitized_note TEXT, created_at_utc TEXT NOT NULL, ticket_version INTEGER NOT NULL
);
CREATE TABLE idempotency_receipts (
 employee_id TEXT NOT NULL, idempotency_key TEXT NOT NULL, request_digest TEXT NOT NULL,
 ticket_id TEXT NOT NULL REFERENCES tickets, response_status INTEGER NOT NULL,
 created_at_utc TEXT NOT NULL, PRIMARY KEY(employee_id, idempotency_key)
);
CREATE TABLE analytics_threads (
 analytics_thread_id TEXT PRIMARY KEY, owner_employee_id TEXT NOT NULL,
 created_at_utc TEXT NOT NULL, updated_at_utc TEXT NOT NULL, sanitized_context_json TEXT NOT NULL
);
