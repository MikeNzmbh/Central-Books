/**
 * Agentic Run List
 * 
 * Displays a list of workflow runs with status badges.
 */

import React from 'react';

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

interface Props {
    runs: WorkflowRun[];
    selectedId: string | null;
    onSelect: (id: string) => void;
    loading: boolean;
}

const AgenticRunList: React.FC<Props> = ({ runs, selectedId, onSelect, loading }) => {
    const getStatusColor = (status: string) => {
        switch (status.toLowerCase()) {
            case 'success':
                return 'status-success';
            case 'failed':
                return 'status-failed';
            case 'partial':
                return 'status-partial';
            case 'running':
                return 'status-running';
            default:
                return 'status-pending';
        }
    };

    const formatTime = (isoString: string) => {
        const date = new Date(isoString);
        return date.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    if (loading) {
        return (
            <div className="run-list">
                <div className="run-list-header">
                    <h3>Workflow Runs</h3>
                </div>
                <div className="loading-state">
                    <div className="spinner"></div>
                    <span>Loading runs...</span>
                </div>
            </div>
        );
    }

    return (
        <div className="run-list">
            <div className="run-list-header">
                <h3>Workflow Runs</h3>
                <span className="run-count">{runs.length}</span>
            </div>

            {runs.length === 0 ? (
                <div className="empty-state">
                    <p>No workflow runs yet</p>
                    <span>Run a workflow to see results here</span>
                </div>
            ) : (
                <ul className="run-items">
                    {runs.map((run) => (
                        <li
                            key={run.id}
                            className={`run-item ${selectedId === run.id ? 'selected' : ''}`}
                            onClick={() => onSelect(run.id)}
                        >
                            <div className="run-item-header">
                                <span className={`status-badge ${getStatusColor(run.status)}`}>
                                    {run.status}
                                </span>
                                <span className="run-time">{formatTime(run.started_at)}</span>
                            </div>
                            <div className="run-item-name">{run.workflow_name}</div>
                            <div className="run-item-meta">
                                <span>{run.step_count} steps</span>
                                <span>•</span>
                                <span>{run.document_count} docs</span>
                                <span>•</span>
                                <span>{run.duration_ms.toFixed(1)}ms</span>
                            </div>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
};

export default AgenticRunList;
