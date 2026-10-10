-- Source datasets are immutable inputs. App connections must use mode=ro.
PRAGMA foreign_keys = ON;
PRAGMA user_version = 1;

CREATE TABLE store_master (
    store_id TEXT PRIMARY KEY,
    store_name TEXT NOT NULL,
    city TEXT NOT NULL,
    region TEXT NOT NULL,
    pos_registers INTEGER NOT NULL CHECK (pos_registers >= 0),
    avg_daily_traffic INTEGER NOT NULL CHECK (avg_daily_traffic >= 0),
    nearby_store_id TEXT REFERENCES store_master(store_id) DEFERRABLE INITIALLY DEFERRED
) STRICT;

CREATE TABLE vendor_master (
    vendor_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    on_time_rate REAL NOT NULL CHECK (on_time_rate BETWEEN 0 AND 1),
    fill_rate REAL NOT NULL CHECK (fill_rate BETWEEN 0 AND 1),
    effective_from TEXT NOT NULL,
    status TEXT NOT NULL,
    primary_category TEXT NOT NULL
) STRICT;

CREATE TABLE product_master (
    sku TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    vendor_id TEXT NOT NULL REFERENCES vendor_master(vendor_id),
    list_price REAL NOT NULL CHECK (list_price >= 0),
    shelf_life_days INTEGER NOT NULL CHECK (shelf_life_days >= 0),
    storage_type TEXT NOT NULL,
    high_demand INTEGER NOT NULL CHECK (high_demand IN (0, 1)),
    warranty_days INTEGER NOT NULL CHECK (warranty_days >= 0)
) STRICT;

CREATE TABLE employee_master (
    employee_id TEXT PRIMARY KEY,
    employee_name TEXT NOT NULL,
    role TEXT NOT NULL,
    store_id TEXT NOT NULL REFERENCES store_master(store_id),
    escalation_level INTEGER NOT NULL CHECK (escalation_level >= 0)
) STRICT;

CREATE TABLE inventory (
    store_id TEXT NOT NULL REFERENCES store_master(store_id),
    sku TEXT NOT NULL REFERENCES product_master(sku),
    on_hand INTEGER NOT NULL CHECK (on_hand >= 0),
    system_qty INTEGER NOT NULL CHECK (system_qty >= 0),
    reorder_point INTEGER NOT NULL CHECK (reorder_point >= 0),
    last_count_date TEXT NOT NULL,
    shelf_capacity INTEGER NOT NULL CHECK (shelf_capacity >= 0),
    PRIMARY KEY (store_id, sku)
) STRICT;

CREATE TABLE receipts (
    receipt_id TEXT PRIMARY KEY,
    store_id TEXT NOT NULL REFERENCES store_master(store_id),
    sku TEXT NOT NULL REFERENCES product_master(sku),
    vendor_id TEXT NOT NULL REFERENCES vendor_master(vendor_id),
    po_qty INTEGER NOT NULL CHECK (po_qty >= 0),
    received_qty INTEGER NOT NULL CHECK (received_qty >= 0),
    receipt_date TEXT NOT NULL,
    quality_check_ok INTEGER NOT NULL CHECK (quality_check_ok IN (0, 1)),
    damage_notes TEXT
) STRICT;

CREATE TABLE returns_quality (
    return_id TEXT PRIMARY KEY,
    created_ts TEXT NOT NULL,
    store_id TEXT NOT NULL REFERENCES store_master(store_id),
    sku TEXT NOT NULL REFERENCES product_master(sku),
    reason TEXT NOT NULL,
    refund_amount_inr REAL NOT NULL CHECK (refund_amount_inr >= 0),
    receipt_present INTEGER NOT NULL CHECK (receipt_present IN (0, 1)),
    status TEXT NOT NULL,
    notes TEXT
) STRICT;

CREATE TABLE support_cases (
    case_id TEXT PRIMARY KEY,
    created_ts TEXT NOT NULL,
    store_id TEXT NOT NULL REFERENCES store_master(store_id),
    employee_id TEXT NOT NULL REFERENCES employee_master(employee_id),
    role TEXT NOT NULL,
    issue_text TEXT NOT NULL,
    sku TEXT REFERENCES product_master(sku),
    category_label TEXT NOT NULL,
    priority_label TEXT NOT NULL CHECK (priority_label IN ('P1', 'P2', 'P3', 'P4')),
    status TEXT NOT NULL,
    register_id TEXT,
    root_cause_hint TEXT
) STRICT;

CREATE TABLE escalation_matrix (
    category TEXT NOT NULL,
    trigger TEXT NOT NULL,
    priority TEXT NOT NULL CHECK (priority IN ('P1', 'P2', 'P3', 'P4')),
    team TEXT NOT NULL,
    channel TEXT NOT NULL,
    sla_minutes INTEGER NOT NULL CHECK (sla_minutes > 0),
    human_approval_required INTEGER NOT NULL CHECK (human_approval_required IN (0, 1)),
    policy_source TEXT NOT NULL,
    PRIMARY KEY (category, trigger)
) STRICT;

CREATE TABLE import_manifest (
    table_name TEXT PRIMARY KEY,
    source_file TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    source_sha256 TEXT NOT NULL,
    imported_at_utc TEXT NOT NULL
) STRICT;

CREATE INDEX ix_cases_time_priority_status ON support_cases(created_ts, priority_label, status);
CREATE INDEX ix_cases_store_sku ON support_cases(store_id, sku);
CREATE INDEX ix_cases_sku_time ON support_cases(sku, created_ts);
CREATE INDEX ix_receipts_store_sku_date ON receipts(store_id, sku, receipt_date);
CREATE INDEX ix_receipts_vendor_date ON receipts(vendor_id, receipt_date);
CREATE INDEX ix_returns_sku_time ON returns_quality(sku, created_ts);
CREATE INDEX ix_products_vendor ON product_master(vendor_id);

-- Historical labels are available for reporting, but excluded from model triage evidence.
CREATE VIEW case_evidence AS
SELECT case_id, created_ts, store_id, role, issue_text, sku, status, register_id
FROM support_cases;

CREATE VIEW open_high_priority_cases AS
SELECT c.case_id, c.created_ts, c.store_id, s.store_name, s.region,
       c.category_label, c.priority_label, c.status, c.sku
FROM support_cases AS c
JOIN store_master AS s ON s.store_id = c.store_id
WHERE c.priority_label IN ('P1', 'P2') AND c.status IN ('Open', 'In Progress');

CREATE VIEW short_shipments AS
SELECT r.receipt_id, r.store_id, r.sku, p.name AS product_name,
       r.vendor_id, v.name AS vendor_name, r.receipt_date,
       r.po_qty, r.received_qty, r.po_qty - r.received_qty AS shortage_qty,
       CASE WHEN r.po_qty > 0 THEN 1.0 * r.received_qty / r.po_qty END AS receipt_fill_rate
FROM receipts AS r
JOIN product_master AS p ON p.sku = r.sku
JOIN vendor_master AS v ON v.vendor_id = r.vendor_id
WHERE r.received_qty < r.po_qty;
