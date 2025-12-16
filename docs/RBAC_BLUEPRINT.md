# Architectural Blueprint for Central Books: Next-Generation Role-Based Access Control (RBAC) and Security Governance

## Executive Summary

The modern accounting SaaS landscape suffers from a critical architectural decoupling between operational necessity and security governance. Small and Midsize Businesses (SMBs) and accounting firms are currently forced to choose between efficiency—granting staff wide-ranging access to perform daily tasks—and security—restricting access to protect sensitive financial data. This binary trade-off, exemplified by recent failures in incumbent platforms like QuickBooks Online (QBO) and Xero, has created a "permission crisis" where internal data breaches are normalized as the cost of doing business.

This report serves as a definitive architectural specification for Central Books (CERN Books). It proposes a novel **Hybrid RBAC/ABAC (Role-Based / Attribute-Based Access Control)** governance model designed to resolve the systemic rigidities of the market leaders.

Our analysis, grounded in extensive forensic review of user complaints, competitor architectures (NetSuite, Stripe, Xero), and cybersecurity best practices, dictates that Central Books must abandon the "module-based" permission model (e.g., "Access Sales Module") in favor of a **"data-centric" model** (e.g., "Read Invoice where Department matches User").

### Four Pillars of Innovation

1. **Field-Level Masking**: Decoupling the ability to process a transaction from the ability to view the associated asset balance, directly addressing the QBO "May 2024" transparency leak.

2. **Context-Aware Scoping**: Implementing Attribute-Based Access Control (ABAC) to restrict visibility based on location, department, and transaction status, solving the Xero "Invoice Only" reporting blindness.

3. **Immutable Audit Chains**: Replacing the "Delete" paradigm with a "Void/Reversal" ledger architecture to ensure absolute audit integrity, ensuring compliance with SAS 70/SOC 1 standards.

4. **AI-Ready Governance**: Defining a permission containment model for Large Language Models (LLMs) to prevent "Prompt Injection" data leaks as AI agents become standard accounting interfaces.

---

## 1. The Pathology of Access Control: A Forensic Analysis of Market Failures

To engineer a superior system, we must first dissect the failures of the incumbent platforms. The dissatisfaction expressed by the user community is not merely regarding feature gaps; it is a rejection of the philosophy of trust embedded in legacy SaaS architectures.

### 1.1 The QuickBooks Online (QBO) "May 2024" Collapse

In early 2024, Intuit released an update to QuickBooks Online user roles that precipitated a crisis of trust among its user base.

#### 1.1.1 The Transparency Leak: Coupling Entry with Visibility

The core of the user revolt centered on a specific architectural decision: the bundling of "Data Entry" permissions with "financial visibility." Historically, businesses employed junior staff or temporary clerks to perform low-level data entry—scanning receipts, entering bills, or matching bank feed transactions. The business requirement for this role is narrow: **Input data to keep the books current.**

However, the QBO update effectively obliterated the boundary between this operational input and high-level financial oversight. Users reported that standard roles, such as "Receipt Entry" or "Standard User," suddenly gained visibility into the **Company Bank Account Balance** and **Total Liability** figures.

This failure stems from a coarse-grained permission model where `Access_Register` is a binary flag. In QBO's architecture, if a user requires access to the Check Register to classify a transaction (a write operation), the system implicitly grants them read access to the register's metadata, specifically the running balance header.

> For a business owner, revealing the company's total liquidity to a temporary data entry clerk is an internal data breach. It fundamentally undermines the hierarchy of the firm.

#### 1.1.2 The "Admin" Trap and Artificial Scarcity

A secondary failure mode in the QBO ecosystem is the weaponization of user limits to drive up-selling. QBO restricts lower-tier plans to a specific number of "Billable Users."

This pricing strategy creates a perverse incentive structure with severe security implications:

- **The Shared Login Epidemic**: To avoid steep price jumps, SMBs resort to sharing credentials.
- **Audit Trail Obfuscation**: When five employees share a single login, the audit log becomes meaningless.
- **Security Nihilism**: By making proper identity management prohibitively expensive, QBO encourages a culture where password sharing is standard operating procedure.

> **Architectural Implication for Central Books**: User seats should be commoditized. The cost driver should be feature consumption (volume of transactions, advanced reporting), not identity. Central Books must encourage every human actor to have a unique digital identity to preserve the integrity of the audit trail.

### 1.2 The Xero "Invoice Only" Paradox

Xero has attempted to solve the granularity problem with its "Invoice Only" roles. However, this model suffers from **Contextual Blindness**.

#### 1.2.1 The Operational Blindfold

Xero's permission model is rigid. An "Invoice Only (Sales)" user can create invoices but cannot generate reports to see the results of their work. A sales representative entering invoices has a legitimate business need to run a "Sales by Customer" report to track their commissions.

In Xero's current architecture, reporting is often an all-or-nothing permission coupled with "Standard" or "Advisor" roles. To give the salesperson reporting access, the Admin must upgrade them to "Standard," which inadvertently exposes the entire General Ledger.

#### 1.2.2 The "Purchases" Leak

On the Accounts Payable (AP) side, users with "Invoice Only (Purchases)" permissions often gain visibility into all bills in the system. Xero lacks **Resource-Based Access Control**. A department head uploading marketing invoices should not see the CEO's legal bills or travel reimbursements.

### 1.3 The NetSuite Complexity Horizon

At the enterprise end of the spectrum, NetSuite offers virtually infinite configurability, but this introduces the **Complexity Horizon**.

#### 1.3.1 Permission Fatigue

NetSuite's permission list exceeds **630 distinct items**. While this allows for perfect segregation of duties, the cognitive load required to manage it is overwhelming for a mid-market controller.

- **The Excel Dependency**: NetSuite administrators are often forced to maintain external Excel spreadsheets just to map and understand their own permission matrices.
- **Configuration Drift**: Due to the difficulty of configuring custom roles, Admins frequently drift toward "Permission Inflation."

> **Architectural Implication for Central Books**: We must navigate the "Goldilocks Zone"—offering the granularity of NetSuite without its administrative burden, and the usability of Xero without its rigidity. This requires a **Composite Role Architecture**.

---

## 2. Competitive Landscape: Models of Governance

### 2.1 The NetSuite Model: Granular but Heavy

- **Strengths**: Granularity is absolute. Permissions are split into "Lists," "Transactions," "Reports," and "Setup". Levels are "View," "Create," "Edit," and "Full" (Delete).
- **Weaknesses**: The sheer volume of permissions leads to misconfiguration. It assumes a dedicated IT Administrator.

### 2.2 The Stripe Model: Org vs. Account

Stripe separates **Organization-Level roles** from **Account-Level roles**.

- **Organization Role**: Controls the legal entity, payout settings, and team management.
- **Account Role**: Controls the specific business unit or store.
- **Innovation**: This hierarchy allows for complex corporate structures without duplicating users.

> **Relevance**: Central Books should adopt this hierarchical inheritance to support multi-entity accounting firms and franchise businesses.

### 2.3 The Xero/QBO Model: Flat and Module-Based

Both Xero and QBO utilize a "Flat" permission model. Permissions are toggles on a single user object.

- **Weaknesses**: This lacks depth. There is no concept of "Department" scoping or "Field Level" security.

### Table 1: Competitive Feature Matrix

| Feature | QBO | Xero | NetSuite | Stripe | Central Books (Target) |
|---------|-----|------|----------|--------|------------------------|
| Role Granularity | Low (Bundled) | Low (Bundled) | High (630+ Perms) | Medium (Functional) | **High (Atomic + Personas)** |
| Field-Level Masking | No | No | Yes (Scriptable) | No | **Native (Bank Balance Mask)** |
| Resource Scoping | Location Only | No | Subsidiary/Dept | Account-Level | **Attribute-Based (ABAC)** |
| Audit Log Integrity | Weak (Deletable) | Medium | High | High (Ledger) | **Immutable (Append-Only)** |
| Multi-Entity Mgmt | Weak | Weak | Strong (OneWorld) | Strong (Org/Acct) | **Hierarchical Inheritance** |
| Pricing Model | Per User (Seat Cap) | Per User (Seat Cap) | Per User | Usage Based | **Unlimited Seats / Usage** |

---

## 3. Architectural Vision: The "Zero Trust" Accounting Model

Central Books will implement a governance model based on **Zero Trust** principles. Access must be explicitly granted based on the intersection of **Identity**, **Resource**, and **Context**.

### 3.1 Core Philosophy: Decoupling the "Trinity of Access"

Legacy systems conflate three distinct capabilities. Central Books will decouple them:

1. **Visibility (Read)**: Can the user see the record? (Scoped by ABAC tags)
2. **Action (Write/Mutate)**: Can the user create or modify data? (Scoped by Transaction Status)
3. **Approval (State Transition)**: Can the user finalize the transaction? (Scoped by Authority Level)

> **Example**: An AP Clerk can Action (Draft) a bill, but cannot Approve it. They can Visibility (See) the bill they created, but cannot Visibility (See) the bank balance that will pay for it.

### 3.2 Hybrid RBAC/ABAC Architecture

Pure RBAC is rigid. Pure ABAC is complex to manage. Central Books uses a hybrid approach.

- **RBAC (The "What")**: Defines the broad capabilities. Example: "AP Clerk Role" has `bill:create`.
- **ABAC (The "Where" and "When")**: Constrains the capabilities based on attributes. Example: `bill:create` is allowed IF `bill.department == user.department AND bill.amount < $500`.

This allows for policies like: *"Sales Managers can view invoices (RBAC), but only for customers in their Region (ABAC)."*

### 3.3 The Immutable Ledger as Source of Truth

- **No Hard Deletes**: The SQL DELETE command is forbidden on transaction tables. "Deleting" an invoice creates a VOID transaction.
- **Cryptographic Chaining**: Each transaction record contains a hash of the previous record, creating a tamper-evident chain.

---

## 4. Role Taxonomy & Hierarchy

### 4.1 System Roles (The Control Plane)

These roles manage the "Container" of the application, not the financial content.

#### Org Owner (Root Principal)
- **Definition**: The legal owner of the data.
- **Capabilities**: Immutable ownership. Can delete the tenant. Billing management.
- **Constraint**: Cannot perform accounting tasks without explicitly assigning themselves a Functional Role.

#### System Admin (IT Operations)
- **Definition**: Manages users, SSO, Integrations, and Security Policies.
- **Capabilities**: Reset MFA, configure API keys, view System Logs.
- **Critical Restriction**: Cannot view financial data.

#### Compliance Officer (Internal Audit)
- **Definition**: Oversees governance and risk.
- **Capabilities**: View Audit Logs, Configure SoD Rules, Manage Data Retention Policies.
- **Constraint**: Read-Only on financial transactions.

### 4.2 Functional Roles (The Accounting Plane)

#### The "Controller" (Financial Admin)
- **Scope**: Full access to GL, Reporting, Banking, and Tax.
- **Responsibilities**: Month-end close, Chart of Accounts, Tax Filing.
- **SoD Check**: If "Strict SoD" is enabled, the Controller cannot originate payments, only approve them.

#### The "AP Specialist" (Accounts Payable)
**Problem Solved**: Prevents the "Xero Blindness" and QBO "Bank Balance Leak."

- **Capabilities**:
  - Create Bills (Draft/Awaiting Approval)
  - View Bills (Scoped: "Department Only")
  - Edit Vendor Details (Scoped: Address/Contact only)
- **Restrictions**:
  - **Masked**: Bank Account Numbers in Vendor Files
  - **Blocked**: Approve bills > Threshold
  - **Blocked**: View Bank Register Balance

#### The "AR Specialist" (Accounts Receivable)
- **Capabilities**:
  - Create Invoices/Estimates
  - Send Invoices
  - View Aging Reports (Scoped: "My Customers")
- **Restrictions**:
  - **Blocked**: Delete posted invoices (Must issue Credit Memo)
  - **Blocked**: View Global P&L

#### The "Cash Manager" (Treasury)
- **Capabilities**: Bank Feeds, Reconciliations, Fund Transfers.
- **Unique Privilege**: This is the only operational role allowed to unmask `Bank_Account_Balance`.
- **SoD Restriction**: Cannot Create Vendors (prevents the "Fake Vendor" fraud scheme).

### 4.3 External & Limited Roles

#### "External CPA/Bookkeeper"
- **Scope**: Similar to Controller but includes specialized "Reclassify" and "Period Close" tools.
- **Time-Boxing**: Access can be configured to expire.

#### "Auditor" (The "Glass" Role)
- **Scope**: Deep Read-Only access.
- **Unique Privilege**: Can access "Point-in-Time" reporting.

#### "Employee" (Self-Service)
- **Scope**: View own expense reimbursements, own time tracking. Zero ledger visibility.

---

## 5. Comprehensive Permission Matrix

### Table 2: Functional Permission Matrix

| Feature / Object | Controller | Cash Manager | AP Specialist | AR Specialist | Auditor | System Admin |
|------------------|------------|--------------|---------------|---------------|---------|--------------|
| Bank: View Balance | ✅ | ✅ | ❌ (Masked) | ❌ (Masked) | ❌ | ❌ |
| Bank: Reconcile | ✅ | ✅ | ❌ | ❌ | 👁️ | ❌ |
| GL: View P&L / Balance Sheet | ✅ | ✅ | ❌ | ❌ | 👁️ | ❌ |
| GL: Manual Journal Entry | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Sales: Create Invoice | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ |
| Sales: Approve Invoice | ✅ | ❌ | ❌ | ✅ (Limit <$10k) | ❌ | ❌ |
| Sales: View Own Reports | ✅ | ❌ | ❌ | ✅ (Scoped) | 👁️ | ❌ |
| Purch: Create Bill | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| Purch: Edit Vendor Bank | ✅ | ❌ | ❌ (Request) | ❌ | ❌ | ❌ |
| Tax: File Return | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Users: Manage Roles | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| System: API Keys | 👁️ | ❌ | ❌ | ❌ | 👁️ | ✅ |
| Audit Log: View | ✅ | 👁️ | ❌ | ❌ | ✅ | ✅ |

**Legend:**
- ✅ = Full Access
- ❌ = No Access (UI Element Hidden)
- 👁️ = View Only (Read-Only)
- (Request) = Triggers Approval Workflow
- (Masked) = Data returned as `******`

### 5.2 The "View Balance" Pivot: A Technical Solution

The QBO complaint regarding bank balance visibility is solved via **Field-Level Masking**.

**The Mechanism**: The API endpoint for `GET /bank-accounts/{id}` returns a JSON object.

**Logic**: If the user lacks `finance.banking.balance.reveal`, the backend explicitly sets the `current_balance` and `available_balance` fields to `null` or `******`.

**UI Behavior**: The frontend renders the transaction list (for categorization) but suppresses the "Running Balance" column and the "Total Balance" header card.

---

## 6. Safety Guardrails: Preventing Data Loss and Fraud

### 6.1 Segregation of Duties (SoD) Governance

Central Books incorporates a native **SoD Engine** that actively monitors for "Toxic Combinations" of permissions.

### Table 3: Toxic Combinations (SoD Matrix)

| Primary Role/Action | Conflicting Role/Action | Risk Scenario | Mitigation Strategy |
|---------------------|-------------------------|---------------|---------------------|
| Vendor Master Edit | Bill Approval | **The Fake Vendor**: Employee creates a vendor (themselves), approves an invoice, and pays it. | Separate `Vendor:Edit` from `Bill:Approve`. |
| Cash Handling (AR) | Bank Reconciliation | **Lapping/Skimming**: Employee steals cash payment, then manipulates bank rec to hide the discrepancy. | Separate `Payment:Receive` from `Bank:Reconcile`. |
| Create Invoice | Create Credit Memo | **The Write-Off**: Employee pockets payment, then issues a credit memo to "void" the invoice. | Require Approval for all Credit Memos > $0. |
| Payroll Admin | GL Journal Entry | **Ghost Employee**: Employee hides fraudulent payroll expense via manual JE manipulation. | Payroll module must post to locked GL accounts only editable by Controller. |

### 6.2 The "Anti-Delete" Architecture (Data Loss Prevention)

Central Books eliminates the concept of a "Hard Delete" for any financial record.

- **Soft Deletes (Voiding)**: When a user selects "Delete," the system performs a `VOID` operation.
- **Reversal Transactions**: The system generates a linked "Reversal Entry" in the current period.
- **Searchability**: "Deleted" items remain indexable via "Include Voided/Deleted" toggle.

### 6.3 Tax Filing Guardrails

Central Books implements **UX Friction Patterns** to prevent accidental tax filing.

- **The "Draft" Sandbox**: All tax forms default to a `DRAFT` state.
- **Explicit Locking**: A period must be formally "Closed/Locked" before filing.
- **Confirmshaming/Friction**: Protected by a Cognitive Friction Modal requiring typed confirmation phrase or 2FA challenge.

---

## 7. AI & Automation Permission Model

As Central Books integrates AI (LLMs) for tasks like categorization and anomaly detection, we must define **Agentic Permissions** to prevent data leakage via Prompt Injection.

### 7.1 The "Intersection" Principle

A common vulnerability is an AI agent that runs with "System" privileges, allowing any user to ask it, "What is the CEO's salary?"

**Policy**: The AI Agent operates with the **Intersection of Permissions**.

```
Effective_Permissions = Agent_Service_Role ∩ User_Current_Session_Role
```

If the user does not have permission to view the Payroll Table, the AI Agent acts as if that table does not exist.

### 7.2 Scope of Operations for AI

- **Read-Only Analysis**: Agents can read data to generate summaries but cannot perform write operations without explicit confirmation.
- **Draft-Only Execution**: When an AI "Categorizes Expenses," it does not post them. It sets them to a `PROPOSED` state. A human user must "Accept" the AI's proposal. This **"Human-in-the-Loop"** ensures that AI hallucinations do not corrupt the ledger.

---

## 8. Implementation Brief: Technical Specifications

### 8.1 JSON Policy Schema

We utilize a policy structure inspired by AWS IAM, enhanced with ABAC conditions.

```json
{
  "policy_id": "pol_ap_specialist_east_001",
  "name": "AP Specialist (East Region)",
  "version": "1.2",
  "statements": [
    {
      "sid": "AllowBillDrafting",
      "effect": "ALLOW",
      "action": ["bill:create", "bill:edit"],
      "resource": "trn:centralbooks:bill:*",
      "condition": {
        "StringEquals": {
          "bill.status": ["draft", "awaiting_approval"]
        },
        "StringMatch": {
          "bill.department": "${user.attributes.department}"
        }
      }
    },
    {
      "sid": "DenyBankBalanceVisibility",
      "effect": "DENY",
      "action": [
        "bank:view_balance",
        "bank:view_running_balance"
      ],
      "resource": "*"
    },
    {
      "sid": "AllowVendorBankEditWithApproval",
      "effect": "ALLOW",
      "action": ["vendor:edit_payment_details"],
      "resource": "*",
      "workflow_trigger": "approval_workflow_controller_01"
    }
  ]
}
```

### 8.2 Schema Explanation

- **sid (Statement ID)**: Human-readable tag.
- **effect**: `ALLOW` or `DENY`. (Explicit DENY always overrides ALLOW).
- **action**: The specific capability (e.g., `bill:create`).
- **condition**: The ABAC layer.
  - `bill.status`: Constrains edits to unapproved bills.
  - `bill.department`: `"${user.attributes.department}"` ensures the user only sees bills matching their own department tag.
- **workflow_trigger**: A novel extension. Instead of a hard block, this triggers a workflow.

### 8.3 Enforcement Layers

1. **Frontend (React/UI)**: The UI consumes the policy JSON to render or hide components.
2. **API Gateway (Middleware)**: The primary enforcement point. Every API request is intercepted and evaluated.
3. **Database (Row-Level Security)**: For high-stakes data (Payroll), we utilize PostgreSQL Row-Level Security (RLS).

---

## 9. User Experience (UX) Strategy: Making Security Usable

Complex security models fail if they are too difficult to configure. Central Books employs **"Poka-Yoke" (Mistake-Proofing)** UX patterns.

### 9.1 The "Persona Wizard" Onboarding

Instead of presenting a grid of 600 permissions (the NetSuite problem), the "Add User" flow uses a natural language wizard.

- **Prompt**: "What is this user's role?"
- **Options**: "My Accountant," "Salesperson," "Office Manager," "Auditor."
- **Result**: The system applies a pre-configured Composite Role Template.

### 9.2 The "View As" Simulation

- **Feature**: "View As [User Name]"
- **Action**: The Admin's interface temporarily reloads using the exact permission set of the target user.
- **Benefit**: Visual verification of security settings.

### 9.3 The "Ghost" Mode Visualization

When editing a role, the UI provides a visual representation of the app navigation.

- **Visual**: Modules the user cannot access are "Ghosted" (greyed out/crossed out).
- **Impact**: Prevents the "Accidental Admin" problem.

---

## 10. Conclusion

The Central Books permission model represents a fundamental shift from application administration to **governance architecture**. By rejecting the binary trade-offs of QBO (Efficiency vs. Privacy) and the reporting blindness of Xero, Central Books establishes a new standard for the mid-market.

### Core Value Proposition: Safe Delegation

An SMB owner must be able to delegate the task of "entering bills" without delegating the anxiety of "exposing the bank account."

Through **Field-Level Masking**, **Context-Aware Scoping**, and **Immutable Audit Trails**, Central Books delivers a platform where security is not a barrier to operation, but the very foundation of it.

> This architecture transforms the accounting ledger from a simple database into a **trusted fortress for financial truth**.
