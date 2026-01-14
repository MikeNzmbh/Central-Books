CREATE TABLE IF NOT EXISTS companion_ai_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL UNIQUE,
    ai_enabled INTEGER NOT NULL DEFAULT 1,
    kill_switch INTEGER NOT NULL DEFAULT 0,
    ai_mode TEXT NOT NULL DEFAULT 'suggest_only',
    velocity_limit_per_minute INTEGER NOT NULL DEFAULT 50,
    value_breaker_threshold TEXT NOT NULL DEFAULT '1000',
    anomaly_stddev_threshold TEXT NOT NULL DEFAULT '3.0',
    trust_downgrade_rejection_rate TEXT NOT NULL DEFAULT '0.4',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (business_id) REFERENCES core_business(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_companion_ai_settings_business
    ON companion_ai_settings (business_id);

CREATE TABLE IF NOT EXISTS companion_business_policy (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL UNIQUE,
    materiality_threshold TEXT NOT NULL DEFAULT '1000',
    risk_appetite TEXT NOT NULL DEFAULT 'standard',
    commingling_risk_vendors_json TEXT NOT NULL DEFAULT '[]',
    related_entities_json TEXT NOT NULL DEFAULT '[]',
    intercompany_enabled INTEGER NOT NULL DEFAULT 0,
    sector_archetype TEXT NOT NULL DEFAULT 'general',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (business_id) REFERENCES core_business(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_companion_business_policy_business
    ON companion_business_policy (business_id);
