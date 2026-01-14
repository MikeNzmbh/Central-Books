CREATE TABLE IF NOT EXISTS agentic_receipt_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    total_documents INTEGER NOT NULL,
    success_count INTEGER NOT NULL,
    warning_count INTEGER NOT NULL,
    error_count INTEGER NOT NULL,
    metrics_json TEXT NOT NULL DEFAULT '{}',
    llm_explanations_json TEXT NOT NULL DEFAULT '[]',
    llm_ranked_documents_json TEXT NOT NULL DEFAULT '[]',
    llm_suggested_classifications_json TEXT NOT NULL DEFAULT '[]',
    llm_suggested_followups_json TEXT NOT NULL DEFAULT '[]',
    trace_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_agentic_receipt_runs_business
    ON agentic_receipt_runs (business_id, created_at);

CREATE TABLE IF NOT EXISTS agentic_receipt_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    business_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    storage_key TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    extracted_payload_json TEXT NOT NULL DEFAULT '{}',
    proposed_journal_payload_json TEXT NOT NULL DEFAULT '{}',
    audit_flags_json TEXT NOT NULL DEFAULT '[]',
    audit_score REAL,
    risk_level TEXT,
    posted_journal_entry_id INTEGER,
    error_message TEXT,
    work_item_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (run_id) REFERENCES agentic_receipt_runs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_agentic_receipt_documents_run
    ON agentic_receipt_documents (run_id);

CREATE TABLE IF NOT EXISTS agentic_invoice_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    total_documents INTEGER NOT NULL,
    success_count INTEGER NOT NULL,
    warning_count INTEGER NOT NULL,
    error_count INTEGER NOT NULL,
    metrics_json TEXT NOT NULL DEFAULT '{}',
    llm_explanations_json TEXT NOT NULL DEFAULT '[]',
    llm_ranked_documents_json TEXT NOT NULL DEFAULT '[]',
    llm_suggested_followups_json TEXT NOT NULL DEFAULT '[]',
    trace_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_agentic_invoice_runs_business
    ON agentic_invoice_runs (business_id, created_at);

CREATE TABLE IF NOT EXISTS agentic_invoice_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    business_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    storage_key TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    extracted_payload_json TEXT NOT NULL DEFAULT '{}',
    proposed_journal_payload_json TEXT NOT NULL DEFAULT '{}',
    audit_flags_json TEXT NOT NULL DEFAULT '[]',
    audit_score REAL,
    risk_level TEXT,
    posted_journal_entry_id INTEGER,
    error_message TEXT,
    work_item_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (run_id) REFERENCES agentic_invoice_runs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_agentic_invoice_documents_run
    ON agentic_invoice_documents (run_id);
