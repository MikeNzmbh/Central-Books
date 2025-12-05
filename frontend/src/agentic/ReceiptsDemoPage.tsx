import React, { useState } from 'react';

// Types for API response
interface WorkflowStep {
    name: string;
    status: string;
    duration_ms: number;
    error?: string | null;
}

interface JournalLine {
    account_code: string;
    account_name: string;
    side: string;
    amount: string;
    debit?: string;
    credit?: string;
}

interface JournalEntry {
    entry_id: string;
    description: string;
    date: string;
    lines: JournalLine[];
    is_balanced: boolean;
    total_debits: string;
    total_credits: string;
}

interface ExtractedDocument {
    id: string;
    vendor_name: string;
    total_amount: string;
    currency: string;
    category_code: string;
}

interface Transaction {
    id: string;
    description: string;
    amount: string;
    currency: string;
    category_code: string;
}

interface ComplianceIssue {
    code: string;
    message: string;
    severity: string;
}

interface ComplianceResult {
    issues: ComplianceIssue[];
    is_compliant: boolean;
}

interface AuditFinding {
    code: string;
    message: string;
    severity: string;
}

interface AuditReport {
    findings: AuditFinding[];
    risk_level: string;
}

interface WorkflowResult {
    workflow_name: string;
    status: string;
    duration_ms: number;
    steps: WorkflowStep[];
    extracted_documents: ExtractedDocument[];
    transactions: Transaction[];
    journal_entries: JournalEntry[];
    compliance: ComplianceResult | null;
    audit: AuditReport | null;
    summary: string | null;
    notes: string[] | null;
}

interface DocumentInput {
    filename: string;
    content: string;
}

// Status badge component
const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
    const colors: Record<string, string> = {
        success: 'bg-emerald-100 text-emerald-700',
        failed: 'bg-rose-100 text-rose-700',
        error: 'bg-rose-100 text-rose-700',
        skipped: 'bg-slate-100 text-slate-500',
    };
    return (
        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${colors[status] || 'bg-slate-100 text-slate-600'}`}>
            {status}
        </span>
    );
};

// Severity badge
const SeverityBadge: React.FC<{ severity: string }> = ({ severity }) => {
    const colors: Record<string, string> = {
        low: 'bg-blue-100 text-blue-700',
        medium: 'bg-amber-100 text-amber-700',
        high: 'bg-rose-100 text-rose-700',
        critical: 'bg-rose-200 text-rose-800',
        info: 'bg-slate-100 text-slate-600',
    };
    return (
        <span className={`px-2 py-0.5 rounded text-xs font-medium uppercase ${colors[severity] || 'bg-slate-100'}`}>
            {severity}
        </span>
    );
};

// Tab button component
const TabButton: React.FC<{
    active: boolean;
    onClick: () => void;
    children: React.ReactNode;
}> = ({ active, onClick, children }) => (
    <button
        onClick={onClick}
        className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${active
                ? 'bg-white text-slate-900 border-b-2 border-emerald-500'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
    >
        {children}
    </button>
);

export default function ReceiptsDemoPage() {
    const [documents, setDocuments] = useState<DocumentInput[]>([
        { filename: 'office_supplies.pdf', content: 'Office Depot - $89.99 - office supplies' },
    ]);
    const [newFilename, setNewFilename] = useState('');
    const [newContent, setNewContent] = useState('');
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<WorkflowResult | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [activeTab, setActiveTab] = useState<'steps' | 'entries' | 'compliance' | 'raw'>('steps');

    const addDocument = () => {
        if (newFilename.trim() || newContent.trim()) {
            setDocuments([
                ...documents,
                {
                    filename: newFilename.trim() || `document-${documents.length + 1}.pdf`,
                    content: newContent.trim(),
                },
            ]);
            setNewFilename('');
            setNewContent('');
        }
    };

    const removeDocument = (index: number) => {
        setDocuments(documents.filter((_, i) => i !== index));
    };

    const runWorkflow = async () => {
        if (documents.length === 0) {
            setError('Please add at least one document');
            return;
        }

        setLoading(true);
        setError(null);
        setResult(null);

        try {
            const response = await fetch('/agentic/demo/receipts-run/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ documents }),
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || 'Failed to run workflow');
            }

            const data: WorkflowResult = await response.json();
            setResult(data);
            setActiveTab('steps');
        } catch (err) {
            setError(err instanceof Error ? err.message : 'An error occurred');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
            {/* Header */}
            <header className="bg-white border-b border-slate-200 shadow-sm">
                <div className="max-w-6xl mx-auto px-6 py-6">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center">
                            <span className="text-white text-lg">⚡</span>
                        </div>
                        <div>
                            <h1 className="text-2xl font-bold text-slate-900">Agentic Accounting OS</h1>
                            <p className="text-slate-500 text-sm">Receipts Demo — Upload receipts and watch the agentic pipeline run end-to-end</p>
                        </div>
                    </div>
                </div>
            </header>

            <main className="max-w-6xl mx-auto px-6 py-8">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    {/* Input Panel */}
                    <div className="space-y-6">
                        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6">
                            <h2 className="text-lg font-semibold text-slate-900 mb-4">📄 Documents</h2>

                            {/* Current documents */}
                            <div className="space-y-3 mb-4">
                                {documents.map((doc, idx) => (
                                    <div key={idx} className="flex items-start gap-3 p-3 bg-slate-50 rounded-lg">
                                        <div className="flex-1 min-w-0">
                                            <div className="font-medium text-slate-700 text-sm truncate">{doc.filename}</div>
                                            <div className="text-xs text-slate-500 mt-1 truncate">{doc.content || '(no content)'}</div>
                                        </div>
                                        <button
                                            onClick={() => removeDocument(idx)}
                                            className="text-slate-400 hover:text-rose-500 transition-colors"
                                        >
                                            ✕
                                        </button>
                                    </div>
                                ))}
                                {documents.length === 0 && (
                                    <div className="text-center py-8 text-slate-400">
                                        No documents added yet
                                    </div>
                                )}
                            </div>

                            {/* Add new document */}
                            <div className="border-t border-slate-200 pt-4 space-y-3">
                                <input
                                    type="text"
                                    placeholder="Filename (e.g., receipt.pdf)"
                                    value={newFilename}
                                    onChange={(e) => setNewFilename(e.target.value)}
                                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none"
                                />
                                <textarea
                                    placeholder="Content (e.g., Starbucks - $15.50 - client meeting)"
                                    value={newContent}
                                    onChange={(e) => setNewContent(e.target.value)}
                                    rows={2}
                                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none resize-none"
                                />
                                <button
                                    onClick={addDocument}
                                    className="w-full py-2 text-sm font-medium text-emerald-600 bg-emerald-50 hover:bg-emerald-100 rounded-lg transition-colors"
                                >
                                    + Add Document
                                </button>
                            </div>
                        </div>

                        {/* Run button */}
                        <button
                            onClick={runWorkflow}
                            disabled={loading || documents.length === 0}
                            className={`w-full py-4 text-lg font-semibold rounded-xl shadow-sm transition-all ${loading || documents.length === 0
                                    ? 'bg-slate-300 text-slate-500 cursor-not-allowed'
                                    : 'bg-gradient-to-r from-emerald-500 to-teal-600 text-white hover:shadow-md hover:scale-[1.01]'
                                }`}
                        >
                            {loading ? (
                                <span className="flex items-center justify-center gap-2">
                                    <span className="animate-spin">⏳</span> Running Workflow...
                                </span>
                            ) : (
                                '▶ Run Workflow'
                            )}
                        </button>

                        {error && (
                            <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-700 text-sm">
                                ❌ {error}
                            </div>
                        )}
                    </div>

                    {/* Results Panel */}
                    <div className="space-y-6">
                        {result ? (
                            <>
                                {/* Summary Card */}
                                <div className={`p-6 rounded-2xl shadow-sm border ${result.status === 'success'
                                        ? 'bg-gradient-to-br from-emerald-50 to-teal-50 border-emerald-200'
                                        : 'bg-gradient-to-br from-amber-50 to-orange-50 border-amber-200'
                                    }`}>
                                    <div className="flex items-center justify-between mb-2">
                                        <h3 className="font-semibold text-slate-900">{result.workflow_name}</h3>
                                        <StatusBadge status={result.status} />
                                    </div>
                                    <p className="text-slate-600 text-sm">{result.summary}</p>
                                    <div className="mt-3 text-xs text-slate-500">
                                        Duration: {result.duration_ms.toFixed(2)}ms
                                    </div>
                                    {result.notes && result.notes.length > 0 && (
                                        <div className="mt-3 space-y-1">
                                            {result.notes.map((note, i) => (
                                                <div key={i} className="text-xs text-amber-700 bg-amber-100 px-2 py-1 rounded">
                                                    ⚠️ {note}
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>

                                {/* Tabs */}
                                <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
                                    <div className="flex gap-1 p-2 bg-slate-50 border-b border-slate-200">
                                        <TabButton active={activeTab === 'steps'} onClick={() => setActiveTab('steps')}>
                                            Steps
                                        </TabButton>
                                        <TabButton active={activeTab === 'entries'} onClick={() => setActiveTab('entries')}>
                                            Journal Entries
                                        </TabButton>
                                        <TabButton active={activeTab === 'compliance'} onClick={() => setActiveTab('compliance')}>
                                            Compliance & Audit
                                        </TabButton>
                                        <TabButton active={activeTab === 'raw'} onClick={() => setActiveTab('raw')}>
                                            Raw JSON
                                        </TabButton>
                                    </div>

                                    <div className="p-6">
                                        {/* Steps Tab */}
                                        {activeTab === 'steps' && (
                                            <div className="space-y-3">
                                                {result.steps.map((step, idx) => (
                                                    <div key={idx} className="flex items-center gap-4 p-3 bg-slate-50 rounded-lg">
                                                        <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm ${step.status === 'success'
                                                                ? 'bg-emerald-100 text-emerald-600'
                                                                : 'bg-rose-100 text-rose-600'
                                                            }`}>
                                                            {step.status === 'success' ? '✓' : '✕'}
                                                        </div>
                                                        <div className="flex-1">
                                                            <div className="font-medium text-slate-700">{step.name}</div>
                                                            <div className="text-xs text-slate-500">{step.duration_ms.toFixed(2)}ms</div>
                                                        </div>
                                                        <StatusBadge status={step.status} />
                                                    </div>
                                                ))}
                                            </div>
                                        )}

                                        {/* Journal Entries Tab */}
                                        {activeTab === 'entries' && (
                                            <div className="space-y-4">
                                                {result.journal_entries.map((entry, idx) => (
                                                    <div key={idx} className="border border-slate-200 rounded-lg overflow-hidden">
                                                        <div className="p-3 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
                                                            <div>
                                                                <div className="font-medium text-slate-700">{entry.description}</div>
                                                                <div className="text-xs text-slate-500">{entry.date}</div>
                                                            </div>
                                                            <span className={`text-sm ${entry.is_balanced ? 'text-emerald-600' : 'text-rose-600'}`}>
                                                                {entry.is_balanced ? '✓ Balanced' : '✕ Unbalanced'}
                                                            </span>
                                                        </div>
                                                        <table className="w-full text-sm">
                                                            <thead className="bg-slate-100">
                                                                <tr>
                                                                    <th className="px-3 py-2 text-left text-slate-600">Account</th>
                                                                    <th className="px-3 py-2 text-right text-slate-600">Debit</th>
                                                                    <th className="px-3 py-2 text-right text-slate-600">Credit</th>
                                                                </tr>
                                                            </thead>
                                                            <tbody>
                                                                {entry.lines.map((line, lineIdx) => (
                                                                    <tr key={lineIdx} className="border-t border-slate-100">
                                                                        <td className="px-3 py-2">
                                                                            <span className="font-mono text-xs text-slate-500">{line.account_code}</span>
                                                                            <span className="ml-2 text-slate-700">{line.account_name}</span>
                                                                        </td>
                                                                        <td className="px-3 py-2 text-right text-slate-700">
                                                                            {line.side === 'debit' && `$${line.amount}`}
                                                                        </td>
                                                                        <td className="px-3 py-2 text-right text-slate-700">
                                                                            {line.side === 'credit' && `$${line.amount}`}
                                                                        </td>
                                                                    </tr>
                                                                ))}
                                                            </tbody>
                                                            <tfoot className="bg-slate-50 font-medium">
                                                                <tr>
                                                                    <td className="px-3 py-2 text-slate-600">Total</td>
                                                                    <td className="px-3 py-2 text-right text-slate-700">${entry.total_debits}</td>
                                                                    <td className="px-3 py-2 text-right text-slate-700">${entry.total_credits}</td>
                                                                </tr>
                                                            </tfoot>
                                                        </table>
                                                    </div>
                                                ))}
                                                {result.journal_entries.length === 0 && (
                                                    <div className="text-center py-8 text-slate-400">No journal entries</div>
                                                )}
                                            </div>
                                        )}

                                        {/* Compliance & Audit Tab */}
                                        {activeTab === 'compliance' && (
                                            <div className="space-y-6">
                                                {/* Compliance */}
                                                <div className="border border-slate-200 rounded-lg p-4">
                                                    <div className="flex items-center justify-between mb-3">
                                                        <h4 className="font-semibold text-slate-900">Compliance Check</h4>
                                                        <span className={`text-2xl ${result.compliance?.is_compliant ? '' : ''}`}>
                                                            {result.compliance?.is_compliant ? '✅' : '❌'}
                                                        </span>
                                                    </div>
                                                    {result.compliance?.issues && result.compliance.issues.length > 0 ? (
                                                        <div className="space-y-2">
                                                            {result.compliance.issues.map((issue, i) => (
                                                                <div key={i} className="p-2 bg-slate-50 rounded flex items-start gap-2">
                                                                    <SeverityBadge severity={issue.severity} />
                                                                    <div>
                                                                        <div className="font-medium text-sm text-slate-700">{issue.code}</div>
                                                                        <div className="text-xs text-slate-500">{issue.message}</div>
                                                                    </div>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    ) : (
                                                        <div className="text-sm text-emerald-600">All compliance checks passed ✓</div>
                                                    )}
                                                </div>

                                                {/* Audit */}
                                                <div className="border border-slate-200 rounded-lg p-4">
                                                    <div className="flex items-center justify-between mb-3">
                                                        <h4 className="font-semibold text-slate-900">Audit Report</h4>
                                                        <SeverityBadge severity={result.audit?.risk_level || 'low'} />
                                                    </div>
                                                    {result.audit?.findings && result.audit.findings.length > 0 ? (
                                                        <div className="space-y-2">
                                                            {result.audit.findings.map((finding, i) => (
                                                                <div key={i} className="p-2 bg-slate-50 rounded flex items-start gap-2">
                                                                    <SeverityBadge severity={finding.severity} />
                                                                    <div>
                                                                        <div className="font-medium text-sm text-slate-700">{finding.code}</div>
                                                                        <div className="text-xs text-slate-500">{finding.message}</div>
                                                                    </div>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    ) : (
                                                        <div className="text-sm text-emerald-600">No audit findings ✓</div>
                                                    )}
                                                </div>
                                            </div>
                                        )}

                                        {/* Raw JSON Tab */}
                                        {activeTab === 'raw' && (
                                            <pre className="p-4 bg-slate-900 text-slate-100 rounded-lg text-xs overflow-auto max-h-96">
                                                {JSON.stringify(result, null, 2)}
                                            </pre>
                                        )}
                                    </div>
                                </div>
                            </>
                        ) : (
                            <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-12 text-center">
                                <div className="text-5xl mb-4">📊</div>
                                <h3 className="text-lg font-medium text-slate-700 mb-2">Ready to Process</h3>
                                <p className="text-slate-500 text-sm">
                                    Add documents and click "Run Workflow" to see the agentic pipeline in action
                                </p>
                            </div>
                        )}
                    </div>
                </div>
            </main>

            {/* Footer */}
            <footer className="border-t border-slate-200 bg-white mt-12">
                <div className="max-w-6xl mx-auto px-6 py-4 text-center text-sm text-slate-500">
                    Agentic Accounting OS — Built for Residency Demo
                </div>
            </footer>
        </div>
    );
}
