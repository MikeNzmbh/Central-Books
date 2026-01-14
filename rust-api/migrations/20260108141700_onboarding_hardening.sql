-- Onboarding Schema Hardening Migration
-- Version: 1.1
-- Created: 2026-01-08
-- Purpose: Add missing indexes, idempotency columns, and startup verification

-- ============================================================================
-- 1. Add composite index for ai_rules queries (business + type + created)
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_ai_rules_business_type_created 
ON ai_rules(business_id, rule_type, created_at DESC);

-- ============================================================================
-- 2. Add composite index for onboarding_events (business + created DESC)
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_onboarding_events_business_created 
ON onboarding_events(business_id, created_at DESC);

-- ============================================================================
-- 3. Add client_event_id for event idempotency (optional dedup key)
-- ============================================================================
ALTER TABLE onboarding_events ADD COLUMN client_event_id TEXT;

-- Create unique index for idempotency (only when client_event_id is provided)
CREATE UNIQUE INDEX IF NOT EXISTS idx_onboarding_events_client_event_id 
ON onboarding_events(business_id, client_event_id) WHERE client_event_id IS NOT NULL;

-- ============================================================================
-- 4. Add rule_hash column for AI rules deduplication
-- ============================================================================
ALTER TABLE ai_rules ADD COLUMN rule_hash TEXT;

-- Index for rule deduplication lookups
CREATE INDEX IF NOT EXISTS idx_ai_rules_hash ON ai_rules(business_id, rule_hash);

-- ============================================================================
-- 5. Add onboarding_variant to business_profiles for analytics
-- ============================================================================
ALTER TABLE business_profiles ADD COLUMN onboarding_variant TEXT DEFAULT 'fast';

-- ============================================================================
-- 6. Startup verification marker table (lightweight check)
-- ============================================================================
CREATE TABLE IF NOT EXISTS _onboarding_schema_version (
    version TEXT NOT NULL,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT INTO _onboarding_schema_version (version) VALUES ('1.1');
