import React, { useState, useEffect } from 'react';

interface JournalLine {
    id: number;
    account_id: number;
    account_name: string;
    account_code: string;
    debit: string;
    credit: string;
    description: string;
}

interface JournalEntry {
    id: number;
    date: string;
    description: string;
    is_void: boolean;
    source_type: string | null;
    source_label: string | null;
    source_object_id: number | null;
    total_debit: string;
    total_credit: string;
    lines: JournalLine[];
    created_at: string | null;
}

interface Stats {
    total_entries: number;
    ytd_entries: number;
    mtd_entries: number;
}

interface SourceChoice {
    value: string;
    label: string;
}

interface JournalData {
    entries: JournalEntry[];
    stats: Stats;
    source_choices: SourceChoice[];
    currency: string;
}

const formatCurrency = (value: string, currency: string): string => {
    const num = parseFloat(value) || 0;
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: currency || 'USD',
        minimumFractionDigits: 2,
    }).format(num);
};

const formatDate = (dateStr: string): string => {
    return new Date(dateStr).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
    });
};

const getSourceIcon = (sourceType: string | null): string => {
    switch (sourceType) {
        case 'invoice': return '📄';
        case 'expense': return '💸';
        case 'banktransaction': return '🏦';
        case 'receipt': return '🧾';
        default: return '📋';
    }
};

export const JournalEntriesPage: React.FC = () => {
    const [data, setData] = useState<JournalData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [searchQuery, setSearchQuery] = useState('');
    const [sourceFilter, setSourceFilter] = useState('all');
    const [showVoid, setShowVoid] = useState(false);
    const [selectedEntry, setSelectedEntry] = useState<JournalEntry | null>(null);

    const fetchData = async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            if (searchQuery) params.set('q', searchQuery);
            if (sourceFilter !== 'all') params.set('source', sourceFilter);
            if (showVoid) params.set('show_void', 'true');

            const response = await fetch(`/api/journal/list/?${params.toString()}`);
            if (!response.ok) throw new Error('Failed to fetch journal entries');
            const json = await response.json();
            setData(json);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, [sourceFilter, showVoid]);

    useEffect(() => {
        const debounce = setTimeout(() => {
            fetchData();
        }, 300);
        return () => clearTimeout(debounce);
    }, [searchQuery]);

    if (loading && !data) {
        return (
            <div className="page-container">
                <div className="loading-spinner">Loading journal entries...</div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="page-container">
                <div className="error-state">Error: {error}</div>
            </div>
        );
    }

    const currency = data?.currency || 'USD';
    const stats = data?.stats;
    const entries = data?.entries || [];
    const sourceChoices = data?.source_choices || [];

    return (
        <div className="page-container">
            {/* Header */}
            <div className="page-header">
                <div className="header-content">
                    <h1>📒 Journal Entries</h1>
                </div>
            </div>

            {/* KPI Cards */}
            <div className="kpi-grid">
                <div className="kpi-card">
                    <div className="kpi-label">Total Entries</div>
                    <div className="kpi-value">{stats?.total_entries || 0}</div>
                </div>
                <div className="kpi-card">
                    <div className="kpi-label">YTD Entries</div>
                    <div className="kpi-value">{stats?.ytd_entries || 0}</div>
                </div>
                <div className="kpi-card">
                    <div className="kpi-label">This Month</div>
                    <div className="kpi-value">{stats?.mtd_entries || 0}</div>
                </div>
            </div>

            {/* Filters */}
            <div className="filter-bar">
                <input
                    type="text"
                    className="search-input"
                    placeholder="Search by description..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                />
                <div className="filter-group">
                    <select
                        className="filter-select"
                        value={sourceFilter}
                        onChange={(e) => setSourceFilter(e.target.value)}
                    >
                        <option value="all">All Sources</option>
                        {sourceChoices.map((choice) => (
                            <option key={choice.value} value={choice.value}>
                                {choice.label}
                            </option>
                        ))}
                    </select>
                    <label className="checkbox-label">
                        <input
                            type="checkbox"
                            checked={showVoid}
                            onChange={(e) => setShowVoid(e.target.checked)}
                        />
                        Show Void
                    </label>
                </div>
            </div>

            {/* Main Content */}
            <div className="content-layout">
                {/* Table */}
                <div className="table-container">
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Description</th>
                                <th>Source</th>
                                <th className="text-right">Debit</th>
                                <th className="text-right">Credit</th>
                                <th className="text-center">Lines</th>
                            </tr>
                        </thead>
                        <tbody>
                            {entries.length === 0 ? (
                                <tr>
                                    <td colSpan={6} className="empty-state">
                                        No journal entries found.
                                    </td>
                                </tr>
                            ) : (
                                entries.map((entry) => (
                                    <tr
                                        key={entry.id}
                                        className={`${entry.is_void ? 'void' : ''} ${selectedEntry?.id === entry.id ? 'selected' : ''}`}
                                        onClick={() => setSelectedEntry(entry)}
                                    >
                                        <td className="date">{formatDate(entry.date)}</td>
                                        <td className="description">
                                            {entry.description}
                                            {entry.is_void && <span className="void-badge">VOID</span>}
                                        </td>
                                        <td>
                                            {entry.source_type && (
                                                <span className="source-badge">
                                                    {getSourceIcon(entry.source_type)} {entry.source_label}
                                                </span>
                                            )}
                                        </td>
                                        <td className="text-right debit">
                                            {formatCurrency(entry.total_debit, currency)}
                                        </td>
                                        <td className="text-right credit">
                                            {formatCurrency(entry.total_credit, currency)}
                                        </td>
                                        <td className="text-center">
                                            <span className="lines-count">{entry.lines.length}</span>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>

                {/* Detail Panel */}
                {selectedEntry && (
                    <div className="detail-panel">
                        <div className="panel-header">
                            <h3>Entry #{selectedEntry.id}</h3>
                            <button className="close-btn" onClick={() => setSelectedEntry(null)}>×</button>
                        </div>
                        <div className="panel-content">
                            <div className="detail-section">
                                <h4>Entry Details</h4>
                                <div className="detail-row">
                                    <span className="label">Date</span>
                                    <span className="value">{formatDate(selectedEntry.date)}</span>
                                </div>
                                <div className="detail-row">
                                    <span className="label">Description</span>
                                    <span className="value">{selectedEntry.description}</span>
                                </div>
                                {selectedEntry.source_type && (
                                    <div className="detail-row">
                                        <span className="label">Source</span>
                                        <span className="value">
                                            {getSourceIcon(selectedEntry.source_type)} {selectedEntry.source_label}
                                        </span>
                                    </div>
                                )}
                                <div className="detail-row">
                                    <span className="label">Status</span>
                                    <span className={`value ${selectedEntry.is_void ? 'void-text' : 'active'}`}>
                                        {selectedEntry.is_void ? 'Void' : 'Active'}
                                    </span>
                                </div>
                            </div>

                            <div className="detail-section">
                                <h4>Journal Lines</h4>
                                <div className="lines-table">
                                    <table>
                                        <thead>
                                            <tr>
                                                <th>Account</th>
                                                <th className="text-right">Debit</th>
                                                <th className="text-right">Credit</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {selectedEntry.lines.map((line) => (
                                                <tr key={line.id}>
                                                    <td className="account-cell">
                                                        <span className="account-code">{line.account_code}</span>
                                                        <span className="account-name">{line.account_name}</span>
                                                    </td>
                                                    <td className="text-right debit">
                                                        {parseFloat(line.debit) > 0 ? formatCurrency(line.debit, currency) : '-'}
                                                    </td>
                                                    <td className="text-right credit">
                                                        {parseFloat(line.credit) > 0 ? formatCurrency(line.credit, currency) : '-'}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                        <tfoot>
                                            <tr>
                                                <td><strong>Total</strong></td>
                                                <td className="text-right debit">
                                                    <strong>{formatCurrency(selectedEntry.total_debit, currency)}</strong>
                                                </td>
                                                <td className="text-right credit">
                                                    <strong>{formatCurrency(selectedEntry.total_credit, currency)}</strong>
                                                </td>
                                            </tr>
                                        </tfoot>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            <style>{`
        .page-container {
          padding: 24px;
          max-width: 1600px;
          margin: 0 auto;
        }
        .page-header {
          margin-bottom: 24px;
        }
        .header-content {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .header-content h1 {
          margin: 0;
          font-size: 28px;
          font-weight: 600;
        }
        .kpi-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
          gap: 16px;
          margin-bottom: 24px;
        }
        .kpi-card {
          background: white;
          border-radius: 12px;
          padding: 20px;
          box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .kpi-label {
          font-size: 13px;
          color: #64748b;
          margin-bottom: 8px;
        }
        .kpi-value {
          font-size: 24px;
          font-weight: 600;
          color: #1e293b;
        }
        .filter-bar {
          display: flex;
          gap: 16px;
          margin-bottom: 20px;
          flex-wrap: wrap;
        }
        .filter-group {
          display: flex;
          gap: 12px;
          align-items: center;
        }
        .search-input {
          flex: 1;
          max-width: 300px;
          padding: 10px 14px;
          border: 1px solid #e2e8f0;
          border-radius: 8px;
          font-size: 14px;
        }
        .search-input:focus {
          outline: none;
          border-color: #6366f1;
          box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
        }
        .filter-select {
          padding: 10px 14px;
          border: 1px solid #e2e8f0;
          border-radius: 8px;
          font-size: 14px;
          background: white;
        }
        .checkbox-label {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 14px;
          color: #64748b;
          cursor: pointer;
        }
        .content-layout {
          display: flex;
          gap: 24px;
        }
        .table-container {
          flex: 1;
          background: white;
          border-radius: 12px;
          box-shadow: 0 1px 3px rgba(0,0,0,0.1);
          overflow: hidden;
        }
        .data-table {
          width: 100%;
          border-collapse: collapse;
        }
        .data-table th,
        .data-table td {
          padding: 14px 16px;
          text-align: left;
          border-bottom: 1px solid #f1f5f9;
        }
        .data-table th {
          background: #f8fafc;
          font-weight: 600;
          font-size: 13px;
          color: #64748b;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }
        .data-table tbody tr {
          cursor: pointer;
          transition: background 0.15s;
        }
        .data-table tbody tr:hover {
          background: #f8fafc;
        }
        .data-table tbody tr.selected {
          background: #eef2ff;
        }
        .data-table tbody tr.void {
          opacity: 0.5;
        }
        .text-right { text-align: right; }
        .text-center { text-align: center; }
        .date {
          font-weight: 500;
          color: #1e293b;
          white-space: nowrap;
        }
        .description {
          max-width: 300px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
        .void-badge {
          display: inline-block;
          margin-left: 8px;
          padding: 2px 6px;
          background: #fef2f2;
          color: #dc2626;
          font-size: 10px;
          font-weight: 600;
          border-radius: 4px;
        }
        .source-badge {
          display: inline-block;
          padding: 4px 10px;
          background: #f1f5f9;
          border-radius: 12px;
          font-size: 12px;
        }
        .debit { color: #059669; }
        .credit { color: #dc2626; }
        .lines-count {
          display: inline-block;
          padding: 4px 10px;
          background: #f1f5f9;
          border-radius: 12px;
          font-size: 13px;
          font-weight: 500;
        }
        .empty-state {
          text-align: center;
          padding: 48px;
          color: #64748b;
        }
        .detail-panel {
          width: 420px;
          background: white;
          border-radius: 12px;
          box-shadow: 0 1px 3px rgba(0,0,0,0.1);
          overflow: hidden;
          align-self: flex-start;
        }
        .panel-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 16px 20px;
          border-bottom: 1px solid #f1f5f9;
        }
        .panel-header h3 {
          margin: 0;
          font-size: 16px;
          font-weight: 600;
        }
        .close-btn {
          background: none;
          border: none;
          font-size: 24px;
          cursor: pointer;
          color: #94a3b8;
          line-height: 1;
        }
        .close-btn:hover { color: #64748b; }
        .panel-content {
          padding: 20px;
        }
        .detail-section {
          margin-bottom: 24px;
        }
        .detail-section h4 {
          margin: 0 0 12px 0;
          font-size: 12px;
          font-weight: 600;
          color: #64748b;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }
        .detail-row {
          display: flex;
          justify-content: space-between;
          padding: 8px 0;
          border-bottom: 1px solid #f8fafc;
        }
        .detail-row .label {
          color: #64748b;
          font-size: 14px;
        }
        .detail-row .value {
          font-weight: 500;
          font-size: 14px;
          text-align: right;
          max-width: 200px;
        }
        .void-text { color: #dc2626; }
        .active { color: #059669; }
        .lines-table {
          background: #f8fafc;
          border-radius: 8px;
          overflow: hidden;
        }
        .lines-table table {
          width: 100%;
          border-collapse: collapse;
          font-size: 13px;
        }
        .lines-table th,
        .lines-table td {
          padding: 10px 12px;
          border-bottom: 1px solid #e2e8f0;
        }
        .lines-table th {
          background: #e2e8f0;
          font-weight: 600;
          font-size: 11px;
          color: #64748b;
          text-transform: uppercase;
        }
        .lines-table tfoot td {
          background: #e2e8f0;
          border-bottom: none;
        }
        .account-cell {
          display: flex;
          flex-direction: column;
          gap: 2px;
        }
        .account-code {
          font-family: monospace;
          font-size: 11px;
          color: #94a3b8;
        }
        .account-name {
          font-weight: 500;
        }
        .loading-spinner, .error-state {
          text-align: center;
          padding: 48px;
          color: #64748b;
        }
        .error-state { color: #dc2626; }
      `}</style>
        </div>
    );
};

export default JournalEntriesPage;
