/**
 * Agentic Console Page
 * 
 * Main container for the agentic workflow console.
 * Shows workflow runs, details, and outputs.
 */

import React, { useState, useEffect } from 'react';
import AgenticRunList from './AgenticRunList';
import AgenticRunDetail from './AgenticRunDetail';
import './AgenticConsole.css';

interface WorkflowRun {
    id: string;
    workflow_name: string;
    status: string;
    started_at: string;
    finished_at?: string;
    duration_ms: number;
    step_count: number;
    document_count: number;
}

const AgenticConsolePage: React.FC = () => {
    const [runs, setRuns] = useState<WorkflowRun[]>([]);
    const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        fetchRuns();
    }, []);

    const fetchRuns = async () => {
        try {
            setLoading(true);
            const response = await fetch('/agentic/demo/runs/');
            if (!response.ok) {
                throw new Error('Failed to fetch runs');
            }
            const data = await response.json();
            setRuns(data.runs || []);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error');
        } finally {
            setLoading(false);
        }
    };

    const handleSelectRun = (runId: string) => {
        setSelectedRunId(runId);
    };

    const handleRefresh = () => {
        fetchRuns();
        setSelectedRunId(null);
    };

    return (
        <div className="agentic-console">
            <header className="console-header">
                <div className="header-left">
                    <h1>Agentic Console</h1>
                    <span className="header-subtitle">Workflow Execution Monitor</span>
                </div>
                <div className="header-right">
                    <button className="refresh-btn" onClick={handleRefresh}>
                        ↻ Refresh
                    </button>
                </div>
            </header>

            <div className="console-content">
                {error && (
                    <div className="error-banner">
                        {error}
                        <button onClick={() => setError(null)}>×</button>
                    </div>
                )}

                <div className="console-layout">
                    <aside className="run-list-panel">
                        <AgenticRunList
                            runs={runs}
                            selectedId={selectedRunId}
                            onSelect={handleSelectRun}
                            loading={loading}
                        />
                    </aside>

                    <main className="run-detail-panel">
                        {selectedRunId ? (
                            <AgenticRunDetail runId={selectedRunId} />
                        ) : (
                            <div className="no-selection">
                                <div className="no-selection-icon">📊</div>
                                <h2>Select a Workflow Run</h2>
                                <p>Choose a run from the list to view details</p>
                            </div>
                        )}
                    </main>
                </div>
            </div>
        </div>
    );
};

export default AgenticConsolePage;
