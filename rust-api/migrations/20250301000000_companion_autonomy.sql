CREATE TABLE companion_autonomy_work_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    business_id INTEGER NOT NULL,
    work_type TEXT NOT NULL,
    surface TEXT NOT NULL,
    status TEXT NOT NULL,
    priority INTEGER NOT NULL,
    dedupe_key TEXT NOT NULL,
    inputs_json TEXT NOT NULL,
    state_json TEXT NOT NULL,
    due_at TEXT,
    snoozed_until TEXT,
    risk_level TEXT NOT NULL,
    confidence_score REAL NOT NULL,
    requires_approval INTEGER NOT NULL,
    customer_title TEXT NOT NULL,
    customer_summary TEXT NOT NULL,
    internal_title TEXT NOT NULL,
    internal_notes TEXT NOT NULL,
    links_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(tenant_id, dedupe_key)
);

CREATE TABLE companion_autonomy_action_recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    business_id INTEGER NOT NULL,
    work_item_id INTEGER NOT NULL,
    action_kind TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    preview_effects_json TEXT NOT NULL,
    status TEXT NOT NULL,
    requires_confirm INTEGER NOT NULL,
    approval_request_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(work_item_id, action_kind)
);

CREATE TABLE companion_autonomy_approval_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    business_id INTEGER NOT NULL,
    work_item_id INTEGER NOT NULL,
    requested_by TEXT NOT NULL,
    status TEXT NOT NULL,
    approved_by INTEGER,
    reason_required INTEGER NOT NULL,
    reason_text TEXT,
    expires_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE companion_autonomy_rationale_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    business_id INTEGER NOT NULL,
    work_item_id INTEGER NOT NULL,
    sections_json TEXT NOT NULL,
    customer_safe_text TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    version INTEGER NOT NULL
);

CREATE TABLE companion_autonomy_claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    business_id INTEGER NOT NULL,
    work_item_id INTEGER NOT NULL,
    statement TEXT NOT NULL,
    confidence REAL NOT NULL,
    verification_status TEXT NOT NULL,
    source_quality_score REAL NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE companion_autonomy_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    business_id INTEGER NOT NULL,
    work_item_id INTEGER NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    excerpt_hash TEXT NOT NULL,
    credibility_flags TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE companion_autonomy_claim_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id INTEGER NOT NULL,
    evidence_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(claim_id, evidence_id)
);

CREATE TABLE companion_autonomy_agent_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    business_id INTEGER NOT NULL,
    work_item_id INTEGER,
    agent_name TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    max_tokens INTEGER NOT NULL,
    max_tool_calls INTEGER NOT NULL,
    max_seconds INTEGER NOT NULL,
    inputs_hash TEXT NOT NULL,
    outputs_json TEXT,
    error_code TEXT,
    error_detail TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE companion_autonomy_tool_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    business_id INTEGER NOT NULL,
    agent_run_id INTEGER,
    tool_name TEXT NOT NULL,
    provider TEXT NOT NULL,
    request_meta TEXT NOT NULL,
    response_meta TEXT NOT NULL,
    tokens_used INTEGER NOT NULL,
    cost_estimate REAL NOT NULL,
    duration_ms INTEGER NOT NULL,
    allowlisted INTEGER NOT NULL,
    blocked_reason TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE companion_autonomy_circuit_breaker_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    business_id INTEGER NOT NULL,
    breaker_type TEXT NOT NULL,
    threshold REAL NOT NULL,
    observed_value REAL NOT NULL,
    action_taken TEXT NOT NULL,
    related_work_item_id INTEGER,
    created_at TEXT NOT NULL
);

CREATE TABLE companion_autonomy_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    business_id INTEGER NOT NULL,
    generated_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    stale_after_minutes INTEGER NOT NULL,
    source_version TEXT NOT NULL
);

CREATE TABLE companion_autonomy_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    business_id INTEGER NOT NULL,
    actor_id INTEGER,
    actor_label TEXT NOT NULL,
    action TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_companion_autonomy_work_items_status
    ON companion_autonomy_work_items (tenant_id, status);

CREATE INDEX idx_companion_autonomy_work_items_risk
    ON companion_autonomy_work_items (tenant_id, risk_level);

CREATE INDEX idx_companion_autonomy_action_status
    ON companion_autonomy_action_recommendations (tenant_id, status);

CREATE INDEX idx_companion_autonomy_agent_runs_status
    ON companion_autonomy_agent_runs (tenant_id, status);

CREATE TABLE companion_autonomy_jobs (
    id TEXT PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    priority INTEGER NOT NULL,
    input_json TEXT NOT NULL,
    output_json TEXT,
    error_detail TEXT,
    budget_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE companion_autonomy_queue_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    snapshot_json TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    stale_after_seconds INTEGER NOT NULL
);

CREATE TABLE companion_autonomy_policy (
    tenant_id INTEGER PRIMARY KEY,
    mode TEXT NOT NULL,
    breaker_thresholds_json TEXT NOT NULL,
    allowlists_json TEXT NOT NULL,
    budgets_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_companion_autonomy_jobs_status
    ON companion_autonomy_jobs (tenant_id, status, priority);

CREATE INDEX idx_companion_autonomy_jobs_kind
    ON companion_autonomy_jobs (tenant_id, kind, status);

CREATE INDEX idx_companion_autonomy_queue_snapshot
    ON companion_autonomy_queue_snapshot (tenant_id, generated_at);
