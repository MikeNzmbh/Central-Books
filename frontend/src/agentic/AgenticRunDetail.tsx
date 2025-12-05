/**
 * Agentic Run Detail
 * 
 * Shows detailed view of a workflow run including steps, outputs, and findings.
 */

import React, { useState, useEffect } from 'react';
import AgenticJournalView from './AgenticJournalView';
import AgenticComplianceAuditView from './AgenticComplianceAuditView';
import AgenticJsonView from './AgenticJsonView';

interface StepResult {
    name: string;
    status: string;
    duration_ms: number;
    error?: string;
}

interface RunDetail {
    id: string;
    workflow_name: string;
    status: string;
    started_at: string;
    finished_at?: string;
    duration_ms: number;
    steps: StepResult[];
    artifacts: {
        documents?: any[];
        transactions?: any[];
        journal_entries?: any[];
        compliance_result?: any;
        audit_report?: any;
    };
    messages?: any[];
}

interface Props {
    runId: string;
}

type TabType = 'steps' | 'journal' | 'compliance' | 'raw';

const AgenticRunDetail: React.FC<Props> = ({ runId }) => {
    const [detail, setDetail] = useState<RunDetail | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [activeTab, setActiveTab] = useState<TabType>('steps');

    useEffect(() => {
        fetchDetail();
    }, [runId]);

    const fetchDetail = async () => {
        try {
            setLoading(true);
            const response = await fetch(`/agentic/demo/runs/${runId}/`);
            if (!response.ok) {
                throw new Error('Failed to fetch run details');
            }
            const data = await response.json();
            setDetail(data);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error');
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return (
            <div className="run-detail loading">
                <div className="spinner"></div>
                <span>Loading details...</span>
            </div>
        );
    }

    if (error || !detail) {
        return (
            <div className="run-detail error">
                <p>{error || 'Run not found'}</p>
            </div>
        );
    }

    return (
        <div className="run-detail">
            {/* Header */}
            <header className="detail-header">
                <div className="detail-title">
                    <h2>{detail.workflow_name}</h2>
                    <span className={`status-badge status-${detail.status.toLowerCase()}`}>
                        {detail.status}
                    </span>
                </div>
                <div className="detail-meta">
                    <span>Duration: {detail.duration_ms.toFixed(2)}ms</span>
                    <span>•</span>
                    <span>Steps: {detail.steps.length}</span>
                </div>
            </header>

            {/* Tabs */}
            <nav className="detail-tabs">
                <button
                    className={activeTab === 'steps' ? 'active' : ''}
                    onClick={() => setActiveTab('steps')}
                >
                    Steps Timeline
                </button>
                <button
                    className={activeTab === 'journal' ? 'active' : ''}
                    onClick={() => setActiveTab('journal')}
                >
                    Journal Entries
                </button>
                <button
                    className={activeTab === 'compliance' ? 'active' : ''}
                    onClick={() => setActiveTab('compliance')}
                >
                    Compliance & Audit
                </button>
                <button
                    className={activeTab === 'raw' ? 'active' : ''}
                    onClick={() => setActiveTab('raw')}
                >
                    Raw JSON
                </button>
            </nav>

            {/* Tab Content */}
            <div className="detail-content">
                {activeTab === 'steps' && (
                    <div className="steps-timeline">
                        {detail.steps.map((step, index) => (
                            <div
                                key={step.name}
                                className={`step-item step-${step.status.toLowerCase()}`}
                            >
                                <div className="step-indicator">
                                    <span className="step-number">{index + 1}</span>
                                    <span className={`step-status ${step.status.toLowerCase()}`}>
                                        {step.status === 'success' ? '✓' : step.status === 'failed' ? '✗' : '○'}
                                    </span>
                                </div>
                                <div className="step-content">
                                    <h4>{step.name}</h4>
                                    <span className="step-duration">{step.duration_ms.toFixed(2)}ms</span>
                                    {step.error && (
                                        <p className="step-error">{step.error}</p>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                )}

                {activeTab === 'journal' && (
                    <AgenticJournalView
                        entries={detail.artifacts?.journal_entries || []}
                    />
                )}

                {activeTab === 'compliance' && (
                    <AgenticComplianceAuditView
                        compliance={detail.artifacts?.compliance_result}
                        audit={detail.artifacts?.audit_report}
                    />
                )}

                {activeTab === 'raw' && (
                    <AgenticJsonView data={detail} />
                )}
            </div>
        </div>
    );
};

export default AgenticRunDetail;
