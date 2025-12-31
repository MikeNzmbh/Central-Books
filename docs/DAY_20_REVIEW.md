# Day 20 Review & Analysis
**Companion AI Governance & Internal Admin Operating System**

## Executive Summary

Day 20 represents a **critical architectural pivot** from "smart assistant" to "governed junior accountant." This is not just feature work—it's establishing the foundational safety, compliance, and operational infrastructure that will determine whether Companion AI can scale to production use.

**Key Theme**: Safety + Ops Brain Milestone

---

## 1. Strategic Assessment

### 1.1 What Changed Fundamentally

**Before Day 20:**
- Companion was a helpful AI assistant
- Direct database writes
- Limited safety mechanisms
- Ad-hoc admin tools

**After Day 20:**
- Companion is a **service account with permissions**
- **Shadow Ledger** architecture (proposal → review → apply)
- **Command sourcing** pattern (no direct writes)
- **Production-grade** admin operations console

### 1.2 Why This Matters

This architecture addresses the **core existential risk** of AI accounting systems:

> "How do we prevent AI from silently corrupting the books while maintaining useful automation?"

The answer: **Dual-ledger architecture with provenance tracking and adversarial auditing.**

---

## 2. Companion Blueprint Deep Dive

### 2.1 Core Architectural Principles

**1. Service Account Model**

```
Actor: system_companion_v2
Role: junior_accountant_bot
Permissions:
  READ: bank_feed, invoices, ledger, business_policy
  WRITE: shadow_ledger ONLY
```

This is **brilliant** because:
- Makes AI behavior auditable (all actions have an actor)
- Enables RBAC enforcement (AI has limited permissions)
- Allows kill switch (disable the service account)
- Supports versioning (v2, v3 can coexist during migration)

**2. Dual-Ledger Architecture**

| Stream A: Canonical Ledger | Stream B: Shadow Ledger |
|----------------------------|-------------------------|
| Immutable legal truth | AI drafts & proposals |
| Used for reports, tax, audits | Wipeable, replayable |
| Human-approved only | AI can write freely |
| Single source of truth | Safe experimentation |

**3. Command Sourcing Pattern**

```
AI Flow:
1. Bank line ingested → Canonical bank event
2. Companion analyzes → ProposeCategorizationCommand
3. Validator checks → ProvisionalLedgerEvent in Shadow
4. Human reviews → ApplyCategorizationCommand
5. Canonical ledger posts with provenance_id
```

This pattern is **audit gold** because:
- Every AI suggestion is logged
- Human decisions are tracked
- Rejection patterns inform AI improvement
- Full replay capability for debugging

### 2.2 No-Hallucination Contract

**Hard Constraints:**
- ❌ Cannot invent transactions, balances, tax rates
- ❌ Cannot bypass period locks, RBAC, or tax engine
- ❌ Cannot edit canonical history directly

**Required Behaviors:**
- ✅ Say "I don't know" when uncertain
- ✅ Ask for business purpose (meals, commingling)
- ✅ Fall back to Tier 2 (proposal-only) with questions

**Critical Insight:** This contract makes Companion **testable**. You can write assertions like:

```python
def test_companion_respects_period_lock():
    period = lock_period("2024-01")
    result = companion.propose_categorization(txn_in_locked_period)
    assert result.error == "Period is locked"
    assert not shadow_ledger.has_proposal(txn.id)
```

---

## 3. Safety & Governance Architecture

### 3.1 Guardrails System

**Kill Switch** (Two Levels)
- **Global**: Emergency stop across all workspaces
- **Per-Workspace**: Disable for specific customer

**Use Case**: "Customer reports AI miscategorizing payroll → flip workspace kill switch → investigate → fix → re-enable"

**Circuit Breakers** (Four Types)

| Breaker | Trigger | Action |
|--------|---------|--------|
| Velocity | >X actions/minute | Pause AI, alert ops |
| Value | Transaction >$5k | Force Tier 2 review |
| Anomaly | Outlier vs baseline | Block auto-commit |
| Trust | High rejection rate | Downgrade to shadow_only |

**Why This Works:**
- **Velocity** prevents runaway automation
- **Value** protects high-stakes transactions
- **Anomaly** catches drift from normal patterns
- **Trust** creates a feedback loop (bad AI → less autonomy)

### 3.2 KYA (Know Your Agent)

Every AI-originated event must log:

```json
{
  "actor": "system_companion_v2",
  "confidence_score": 0.87,
  "logic_trace_id": "trace_xyz",
  "rationale": "Vendor 'Adobe' matches 80% to Software subcategory",
  "human_reviewed": false,
  "provenance_id": "shadow_evt_123"
}
```

**Compliance Value:**
- SOC2 auditors can trace every AI decision
- SOX requires this level of provenance
- GDPR "right to explanation" satisfied

### 3.3 Adversarial Auditor ("Checker")

**Purpose**: Catch what the AI misses

**Scanning Rules:**
- Payroll/equity/intercompany anomalies
- Suspense account abuse
- Unusual spikes vs historical patterns

**Output**: Weekly integrity reports per workspace

**Architecture Note**: This should be a **separate service** (not part of Companion) to maintain adversarial relationship.

**Implementation Suggestion:**

```python
class AdversarialAuditor:
    \"\"\"Scans canonical ledger for AI-introduced risks\"\"\"
    
    def scan_workspace(self, workspace_id, period):
        flags = []
        
        # Flag 1: AI touched sensitive accounts
        ai_payroll_entries = Entry.objects.filter(
            workspace_id=workspace_id,
            period=period,
            account__category='PAYROLL',
            created_by__startswith='system_companion'
        )
        if ai_payroll_entries.exists():
            flags.append(AuditFlag(
                severity='HIGH',
                reason='AI modified payroll account',
                entries=ai_payroll_entries
            ))
        
        # Flag 2: Suspense accumulation
        # Flag 3: Velocity spikes
        # etc.
        
        return IntegrityReport(flags=flags)
```

---

## 4. Business Profile v2 - Context & Policy

### 4.1 Policy Fields

```python
class BusinessPolicy(models.Model):
    materiality_threshold = models.DecimalField(default=1.00)
    risk_appetite = models.CharField(
        choices=['conservative', 'standard', 'aggressive']
    )
    commingling_risk_vendors = models.JSONField(
        default=list,  # ['Amazon', 'Target', 'Uber', 'Costco']
    )
    related_entities = models.JSONField(default=dict)
    intercompany_enabled = models.BooleanField(default=False)
    sector_archetype = models.CharField(
        choices=['saas', 'ecommerce', 'construction', 'agency']
    )
```

### 4.2 Dynamic Policy Learning

**User Correction Flow:**

```
1. User changes Adobe from Software → COGS
2. Companion detects pattern break
3. Prompt: "Should future Adobe transactions go to COGS?"
4. If yes → Update business policy
5. Future Adobe txns use new policy
```

**Why This Is Powerful:**
- Policy evolves with business reality
- Reduces repeat corrections
- Builds institutional knowledge
- Makes AI more "your accountant" vs "generic AI"

### 4.3 Risk-Based Behavior

| Policy Setting | AI Behavior |
|---------------|-------------|
| High-risk vendor detected | No Tier 1, proposal only |
| Intercompany transaction | Always Tier 2 review |
| Amount > materiality threshold | Force human review |
| Conservative risk appetite | More proposals, less auto-commit |

---

## 5. Internal Admin OS Evolution

### 5.1 Users Page (Designed, Not Yet Implemented)

**Left Panel**: Searchable, filterable user table

**Right Panel**: Rich user details
- Last active, join date, workspace count
- Admin role dropdown (Support/Ops/Superadmin)
- Staff/superuser toggles with warnings
- Impersonation button

**Extended Features:**
- Internal notes (support context)
- AI context card (recent issues, risk flags)

**Assessment**: This turns admin into a **CRM for operations** rather than just user management.

### 5.2 Workspaces Page (God View)

**Table Columns:**
- Name, owner, plan, status
- Unreconciled count
- Ledger status

**Details Panel - "God View":**
- Bank feeds health
- Reconciliation status
- Ledger health flags
- Invoices & expenses summary
- AI mode status (on/off, mode)

**Operations Actions:**
- Edit workspace metadata
- Soft-delete with confirmation
- Override AI settings
- View audit trail

**Why "God View" Matters:**
- Support can diagnose issues without SQL queries
- Proactive health monitoring
- Pattern recognition across workspaces

### 5.3 Audit & Logs Page

**Filters:**
- Actor (human vs system_companion_vX)
- Resource type (user, workspace, ledger, AI)
- Category (security, config, ledger, AI actions)

**Display:**
- Timestamp, action
- Before/after snapshots (where safe)
- IP, user agent

**Compliance Value:**
- SOC2 audit trail requirement: ✅
- SOX change tracking: ✅
- GDPR activity logs: ✅
- Customer dispute resolution: ✅

### 5.4 Approvals & Operations Dashboard

**Approvals Page** (Maker-Checker):
- Refunds
- Ledger corrections
- Settings changes
- Pending/Approved/Rejected queues

**Operations Dashboard** (Ops KPIs):
- Unreconciled items count
- Failed bank feeds
- AI breaker triggers
- Overdue approvals

**Strategic Note**: This becomes the **ops team home screen**, not an afterthought admin panel.

---

## 6. LLM Orchestration Strategy

### 6.1 Role Separation

| Model | Role | Use Cases |
|-------|------|-----------|
| **DeepSeek** | Primary reasoning | Classification, planning, command generation |
| **Gemini** | Research & critique | Blind spots, tech debt, regulatory risks |
| **Codex** | Code execution | Models, migrations, APIs, React pages |

### 6.2 Blueprint as Contract

**Critical Pattern**: `COMPANION_BLUEPRINT.md` becomes the **constitutional document** that all AI agents must respect.

**Enforcement:**

```python
# In AI orchestration layer
def generate_proposal(llm_output):
    proposal = parse_llm_output(llm_output)
    
    # Blueprint enforcement
    assert proposal.target_ledger == 'shadow'
    assert proposal.actor.startswith('system_companion')
    assert proposal.has_rationale()
    
    # Guardrails
    if proposal.amount > CIRCUIT_BREAKER_VALUE:
        proposal.tier = 2  # Force review
    
    return proposal
```

---

## 7. Critical Gaps & Risks

### 7.1 Implementation Gap

**Reality Check**: Day 20 is mostly **architecture and design**, not deployed code.

**What's Spec'd But Not Built:**
- ❌ Shadow Ledger persistence
- ❌ Proposal API endpoints
- ❌ React proposals page
- ❌ Circuit breaker implementation
- ❌ Adversarial auditor service
- ❌ Admin pages (Users, Workspaces, Audit)

**Risk**: Architecture without implementation is vaporware.

**Mitigation**: Days 21-23 focused on vertical slice (proposal flow end-to-end).

### 7.2 Testing Strategy Needed

**Question**: How do you test AI governance?

**Answer**: Need test suite for:
- Kill switch effectiveness
- Circuit breaker triggers
- Adversarial auditor accuracy
- Policy enforcement
- Provenance tracking

**Suggested Approach:**

```python
class CompanionGovernanceTests(TestCase):
    def test_kill_switch_blocks_all_ai_actions(self):
        workspace = create_workspace()
        workspace.ai_settings.kill_switch = True
        
        result = companion.propose_categorization(txn)
        assert result.error == "AI disabled for workspace"
    
    def test_circuit_breaker_large_amount(self):
        txn = create_transaction(amount=10000)
        result = companion.propose_categorization(txn)
        assert result.tier == 2  # Forced review
        assert result.reason == "Circuit breaker: value threshold"
    
    def test_adversarial_auditor_flags_payroll(self):
        # AI proposes payroll entry
        # Human approves (mistake)
        # Auditor should flag in weekly report
        pass
```

### 7.3 Performance Concerns

**Shadow Ledger Growth**: If every AI proposal is persisted, storage grows fast.

**Mitigation Options:**
- TTL on rejected proposals (e.g., 90 days)
- Aggregate old proposals into summary stats
- Archive to cold storage after N days

### 7.4 User Experience Questions

**How does a user interact with Shadow Ledger?**

**Needs Design:**
- Notification of pending proposals
- Bulk approve/reject UI
- "Teach mode" where user corrections update policy
- Confidence score visualization

**Example Flow:**

```
1. User logs in
2. Badge: "12 transactions need review"
3. Proposals page shows:
   - Transaction details
   - AI categorization + confidence
   - "Approve" / "Reject" / "Edit & Apply"
4. User approves → ApplyCommand → Canonical ledger
5. User rejects → Logged for AI retraining
```

---

## 8. Next Steps Assessment (Days 21-23)

### 8.1 Prioritization Review

**Day 21-23 Goals:**
1. ✅ **Critical**: Shadow proposals + Apply/Reject API
2. ✅ **Critical**: AI Settings & Kill Switch UI
3. ⚠️ **Important**: Auditor MVP (could defer to Day 24+)
4. ⚠️ **Important**: Business Profile Wizard (could iterate)
5. ✅ **Critical**: Ops Runbooks

**Recommendation**: Focus on **#1 and #2** to get proposal flow working end-to-end. Auditor and Profile can be Day 24-25.

### 8.2 Vertical Slice Definition

**Minimum Viable Proposal Flow:**

**Backend:**

```python
# models.py
class ProvisionalLedgerEvent(models.Model):
    workspace = models.ForeignKey(Workspace)
    shadow_transaction_id = models.UUIDField()
    actor = models.CharField()  # system_companion_v2
    confidence_score = models.FloatField()
    rationale = models.TextField()
    status = models.CharField(
        choices=['PENDING', 'APPROVED', 'REJECTED']
    )
    
class AppliedProposal(models.Model):
    provisional_event = models.ForeignKey(ProvisionalLedgerEvent)
    canonical_entry_id = models.UUIDField()
    applied_by = models.ForeignKey(User)
    applied_at = models.DateTimeField()
```

**API:**

```python
# GET /api/companion/v2/proposals/
# POST /api/companion/v2/proposals/<id>/apply/
# POST /api/companion/v2/proposals/<id>/reject/
```

**Frontend:**

```tsx
// ProposalsPage.tsx
function ProposalsPage() {
  const proposals = useProposals();
  
  return (
    <div>
      {proposals.map(p => (
        <ProposalCard
          key={p.id}
          proposal={p}
          onApprove={() => applyProposal(p.id)}
          onReject={() => rejectProposal(p.id)}
        />
      ))}
    </div>
  );
}
```

### 8.3 Success Criteria

**By End of Day 23:**
- [ ] User can see list of AI proposals
- [ ] User can approve proposal → writes to canonical ledger
- [ ] User can reject proposal → logged for retraining
- [ ] Kill switch in UI actually stops AI from proposing
- [ ] At least one circuit breaker implemented (value threshold)

---

## 9. Strategic Recommendations

### 9.1 Documentation Priority

**Create These Immediately:**
1. **API Contract**: Shadow Ledger endpoints spec
2. **State Machine Diagram**: Proposal lifecycle
3. **Security Model**: RBAC for Companion service account
4. **Runbook**: "What to do when AI breaker trips"

### 9.2 Staffing Consideration

**Observation**: This work is **systems-level engineering**, not feature development.

**Skills Needed:**
- Event sourcing expertise
- Audit/compliance knowledge
- AI safety understanding
- Operations tooling experience

**Recommendation**: Consider whether current team has capacity/expertise, or if specialized help needed.

### 9.3 Customer Communication

**When to Tell Customers About Shadow Ledger?**

**Option A - Transparent Early**: "We use AI proposals that you review before they affect your books."
- **Pro**: Builds trust, sets expectations
- **Con**: May scare non-technical users

**Option B - Gradual Reveal**: Initially show as "AI suggestions" without exposing full architecture.
- **Pro**: Simpler mental model
- **Con**: May feel like hiding complexity

**Recommendation**: Option A for beta customers, Option B for general release.

### 9.4 Regulatory Positioning

**This architecture is audit gold** because:
- Full provenance tracking (required for SOX)
- Immutable canonical ledger (required for most jurisdictions)
- Human-in-the-loop for material transactions (best practice)
- Adversarial auditor (defense-in-depth)

**Marketing Angle**: "The only AI bookkeeping with true audit trail separation."

---

## 10. Architecture Grade: A-

**What's Excellent:**
- ✅ Shadow Ledger concept is sound
- ✅ Command sourcing is industry best practice
- ✅ Guardrails are comprehensive
- ✅ Service account model is brilliant
- ✅ Adversarial auditor is innovative

**What Needs Work:**
- ⚠️ Implementation gap (design > code)
- ⚠️ Testing strategy undefined
- ⚠️ Performance implications unclear
- ⚠️ User experience needs design

**Overall**: This is **production-grade architecture** if executed well. The foundation is solid.

---

## 11. Comparison to Industry

### 11.1 How This Compares to QuickBooks AI

**QuickBooks Approach** (educated guess):
- Direct writes with AI flag
- Undo feature if wrong
- Limited provenance tracking

**Central Books Approach** (Day 20):
- Shadow Ledger (no direct writes)
- Approve/reject flow
- Full provenance + adversarial audit

**Winner**: Central Books approach is **more conservative** but also **more auditable**.

### 11.2 How This Compares to Stripe Sigma

**Stripe Sigma**: SQL queries on production data with read-only access.

**Central Books Shadow Ledger**: Proposal layer that can't corrupt production.

**Parallel**: Both recognize that **separation of concerns** is critical for safety.

---

## 12. Final Assessment

Day 20 is a milestone because it answers the fundamental question:

> "How do we build AI accounting that auditors will trust?"

**The answer:**
1. Dual ledger (shadow/canonical)
2. Command sourcing (propose/apply)
3. Service account model
4. Adversarial auditing
5. Kill switches & circuit breakers

This is not incremental improvement. This is architectural maturity.

**Recommendation**: Address these before writing line 1 of implementation code.

