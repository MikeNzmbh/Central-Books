/**
 * Agentic Compliance & Audit View
 * 
 * Displays compliance issues and audit findings.
 */

import React from 'react';

interface ComplianceIssue {
    code: string;
    severity: string;
    message: string;
    transaction_id?: string;
}

interface ComplianceResult {
    is_compliant: boolean;
    issues: ComplianceIssue[];
}

interface AuditFinding {
    code: string;
    severity: string;
    message: string;
    transaction_id?: string;
    journal_entry_id?: string;
}

interface AuditReport {
    risk_level: string;
    findings: AuditFinding[];
}

interface Props {
    compliance?: ComplianceResult;
    audit?: AuditReport;
}

const AgenticComplianceAuditView: React.FC<Props> = ({ compliance, audit }) => {
    const getSeverityClass = (severity: string) => {
        switch (severity.toLowerCase()) {
            case 'critical':
                return 'severity-critical';
            case 'high':
                return 'severity-high';
            case 'medium':
                return 'severity-medium';
            case 'low':
                return 'severity-low';
            default:
                return 'severity-info';
        }
    };

    const getRiskClass = (risk: string) => {
        switch (risk.toLowerCase()) {
            case 'high':
                return 'risk-high';
            case 'medium':
                return 'risk-medium';
            default:
                return 'risk-low';
        }
    };

    return (
        <div className="compliance-audit-view">
            {/* Compliance Section */}
            <section className="compliance-section">
                <header className="section-header">
                    <h3>Compliance Check</h3>
                    {compliance && (
                        <span className={`compliance-badge ${compliance.is_compliant ? 'compliant' : 'non-compliant'}`}>
                            {compliance.is_compliant ? '✓ Compliant' : '✗ Issues Found'}
                        </span>
                    )}
                </header>

                {!compliance ? (
                    <p className="no-data">No compliance data available</p>
                ) : compliance.issues.length === 0 ? (
                    <div className="success-state">
                        <span className="success-icon">✓</span>
                        <p>All compliance checks passed</p>
                    </div>
                ) : (
                    <ul className="issues-list">
                        {compliance.issues.map((issue, idx) => (
                            <li key={idx} className={`issue-item ${getSeverityClass(issue.severity)}`}>
                                <div className="issue-header">
                                    <span className="issue-code">{issue.code}</span>
                                    <span className={`severity-badge ${getSeverityClass(issue.severity)}`}>
                                        {issue.severity}
                                    </span>
                                </div>
                                <p className="issue-message">{issue.message}</p>
                                {issue.transaction_id && (
                                    <span className="issue-ref">Ref: {issue.transaction_id}</span>
                                )}
                            </li>
                        ))}
                    </ul>
                )}
            </section>

            {/* Audit Section */}
            <section className="audit-section">
                <header className="section-header">
                    <h3>Audit Report</h3>
                    {audit && (
                        <span className={`risk-badge ${getRiskClass(audit.risk_level)}`}>
                            Risk: {audit.risk_level}
                        </span>
                    )}
                </header>

                {!audit ? (
                    <p className="no-data">No audit data available</p>
                ) : audit.findings.length === 0 ? (
                    <div className="success-state">
                        <span className="success-icon">✓</span>
                        <p>No audit findings</p>
                    </div>
                ) : (
                    <ul className="findings-list">
                        {audit.findings.map((finding, idx) => (
                            <li key={idx} className={`finding-item ${getSeverityClass(finding.severity)}`}>
                                <div className="finding-header">
                                    <span className="finding-code">{finding.code}</span>
                                    <span className={`severity-badge ${getSeverityClass(finding.severity)}`}>
                                        {finding.severity}
                                    </span>
                                </div>
                                <p className="finding-message">{finding.message}</p>
                                {finding.transaction_id && (
                                    <span className="finding-ref">Transaction: {finding.transaction_id}</span>
                                )}
                                {finding.journal_entry_id && (
                                    <span className="finding-ref">Entry: {finding.journal_entry_id}</span>
                                )}
                            </li>
                        ))}
                    </ul>
                )}
            </section>
        </div>
    );
};

export default AgenticComplianceAuditView;
