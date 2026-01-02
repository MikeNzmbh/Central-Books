"""
CLI Demo - Receipts Workflow with Compliance & Audit

Runs the end-to-end receipts workflow and prints human-readable output
including compliance checks and audit findings.

Usage:
    python -m agentic.workflows.cli_receipts_demo
"""

from agentic.workflows.steps.receipts_pipeline import build_receipts_workflow


def main() -> None:
    """Run the receipts workflow demo."""
    # Build workflow
    wf = build_receipts_workflow()

    # Demo input data
    context = {
        "uploaded_files": [
            {"filename": "office_supplies_receipt.pdf", "content": "dummy"},
            {"filename": "coffee_meeting_receipt.pdf", "content": "dummy"},
            {"filename": "software_subscription_invoice.pdf", "content": "dummy"},
        ]
    }

    # Run workflow
    result = wf.run(context)

    # Print results
    print("=" * 60)
    print("Agentic Accounting OS - Receipts Workflow Demo")
    print("=" * 60)
    print()
    print(f"Workflow: {result.workflow_name}")
    print(f"Status: {result.status.upper()}")
    print(f"Started: {result.started_at.isoformat()}")
    print(f"Finished: {result.finished_at.isoformat()}")
    print(f"Duration: {result.duration_ms:.2f}ms")
    print()

    print("Steps:")
    for step in result.steps:
        status_icon = "✓" if step.status == "success" else "✗"
        print(f"  {status_icon} {step.step_name}: {step.status} ({step.duration_ms:.2f}ms)")
        if step.error_message:
            print(f"    Error: {step.error_message}")
    print()

    # Documents
    docs = result.artifacts.get("documents", [])
    print(f"Documents Ingested: {len(docs)}")
    for doc in docs:
        print(f"  - {doc.get('filename', 'unknown')}")
    print()

    # Extracted
    extracted = result.artifacts.get("extracted_documents", [])
    print(f"Documents Extracted: {len(extracted)}")
    for ext in extracted:
        print(f"  - {ext.get('vendor_name', 'unknown')}: ${ext.get('total_amount', 0)}")
    print()

    # Transactions
    txns = result.artifacts.get("transactions", [])
    print(f"Transactions Normalized: {len(txns)}")
    for txn in txns:
        print(f"  - {txn.get('description', '')}: ${txn.get('amount', 0)}")
    print()

    # Journal Entries
    entries = result.artifacts.get("journal_entries", [])
    print(f"Journal Entry Proposals: {len(entries)}")
    for entry in entries:
        print(f"  Entry: {entry.get('description', '')}")
        for line in entry.get("lines", []):
            side = line.get("side", "").upper()
            amount = line.get("amount", "0")
            account = line.get("account_code", "")
            account_name = line.get("account_name", "")
            print(f"    {account} ({account_name}): {side} ${amount}")
        balanced = "✓" if entry.get("is_balanced") else "✗"
        print(f"    Balanced: {balanced}")
    print()

    # Compliance Check
    comp = result.artifacts.get("compliance_result")
    if comp:
        print("-" * 40)
        print("Compliance Check:")
        is_compliant = comp.get("is_compliant", True)
        print(f"  Overall compliant: {'YES ✓' if is_compliant else 'NO ✗'}")
        issues = comp.get("issues", [])
        if issues:
            for issue in issues:
                severity = issue.get("severity", "info").upper()
                code = issue.get("code", "UNKNOWN")
                message = issue.get("message", "")
                print(f"  - [{severity}] {code}: {message}")
        else:
            print("  No issues found.")
        print()

    # Audit Report
    audit = result.artifacts.get("audit_report")
    if audit:
        print("-" * 40)
        print("Audit Report:")
        risk_level = audit.get("risk_level", "low").upper()
        print(f"  Risk level: {risk_level}")
        findings = audit.get("findings", [])
        if findings:
            for finding in findings:
                severity = finding.get("severity", "info").upper()
                code = finding.get("code", "UNKNOWN")
                message = finding.get("message", "")
                print(f"  - [{severity}] {code}: {message}")
        else:
            print("  No findings.")
        print()

    print("=" * 60)
    print("Demo Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
