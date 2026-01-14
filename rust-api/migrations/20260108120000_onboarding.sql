-- Calm Companion Onboarding Schema
-- Version: 1.0
-- Created: 2026-01-08

-- ============================================================================
-- business_profiles: Versioned JSON storage for onboarding data
-- ============================================================================
CREATE TABLE IF NOT EXISTS business_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL UNIQUE,
    profile_json TEXT NOT NULL DEFAULT '{}',
    onboarding_version TEXT NOT NULL DEFAULT '1.0',
    onboarding_status TEXT NOT NULL DEFAULT 'not_started',
    current_step TEXT,
    fast_path INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (business_id) REFERENCES core_business(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_business_profiles_business_id ON business_profiles(business_id);
CREATE INDEX IF NOT EXISTS idx_business_profiles_status ON business_profiles(onboarding_status);

-- ============================================================================
-- consents: User consent tracking with full audit trail
-- ============================================================================
CREATE TABLE IF NOT EXISTS consents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    consent_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    granted_at TEXT,
    revoked_at TEXT,
    metadata_json TEXT DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(business_id, user_id, consent_key),
    FOREIGN KEY (business_id) REFERENCES core_business(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES auth_user(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_consents_business_user ON consents(business_id, user_id);
CREATE INDEX IF NOT EXISTS idx_consents_key ON consents(consent_key);

-- ============================================================================
-- onboarding_events: Analytics telemetry for onboarding flow
-- ============================================================================
CREATE TABLE IF NOT EXISTS onboarding_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    event_name TEXT NOT NULL,
    properties_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (business_id) REFERENCES core_business(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES auth_user(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_onboarding_events_business ON onboarding_events(business_id);
CREATE INDEX IF NOT EXISTS idx_onboarding_events_name ON onboarding_events(event_name);
CREATE INDEX IF NOT EXISTS idx_onboarding_events_created ON onboarding_events(created_at);

-- ============================================================================
-- ai_rules: AI-learned categorization and matching rules
-- ============================================================================
CREATE TABLE IF NOT EXISTS ai_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL,
    rule_type TEXT NOT NULL,
    rule_json TEXT NOT NULL DEFAULT '{}',
    confidence REAL NOT NULL DEFAULT 1.0,
    is_active INTEGER NOT NULL DEFAULT 1,
    source TEXT NOT NULL DEFAULT 'user_confirmed',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (business_id) REFERENCES core_business(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ai_rules_business ON ai_rules(business_id);
CREATE INDEX IF NOT EXISTS idx_ai_rules_type ON ai_rules(rule_type);
CREATE INDEX IF NOT EXISTS idx_ai_rules_active ON ai_rules(is_active);
