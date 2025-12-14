import React, { useState, useEffect } from 'react';

interface Supplier {
    id: number;
    name: string;
    email: string;
    phone: string;
    address: string;
    total_spend: string;
    ytd_spend: string;
    expense_count: number;
}

interface Stats {
    total_suppliers: number;
    total_spend: string;
    ytd_spend: string;
}

interface SupplierData {
    suppliers: Supplier[];
    stats: Stats;
    currency: string;
}

const formatCurrency = (value: string, currency: string): string => {
    const num = parseFloat(value) || 0;
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: currency || 'USD',
    }).format(num);
};

export const SuppliersPage: React.FC = () => {
    const [data, setData] = useState<SupplierData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedSupplier, setSelectedSupplier] = useState<Supplier | null>(null);

    const fetchData = async (query: string = '') => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            if (query) params.set('q', query);
            const response = await fetch(`/api/suppliers/list/?${params.toString()}`);
            if (!response.ok) throw new Error('Failed to fetch suppliers');
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
    }, []);

    useEffect(() => {
        const debounce = setTimeout(() => {
            fetchData(searchQuery);
        }, 300);
        return () => clearTimeout(debounce);
    }, [searchQuery]);

    if (loading && !data) {
        return (
            <div className="page-container">
                <div className="loading-spinner">Loading suppliers...</div>
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
    const suppliers = data?.suppliers || [];

    return (
        <div className="page-container">
            {/* Header */}
            <div className="page-header">
                <div className="header-content">
                    <h1>Suppliers</h1>
                    <a href="/suppliers/new/" className="btn btn-primary">
                        <span className="icon">+</span> New Supplier
                    </a>
                </div>
            </div>

            {/* KPI Cards */}
            <div className="kpi-grid">
                <div className="kpi-card">
                    <div className="kpi-label">Total Suppliers</div>
                    <div className="kpi-value">{stats?.total_suppliers || 0}</div>
                </div>
                <div className="kpi-card">
                    <div className="kpi-label">All-Time Spend</div>
                    <div className="kpi-value expense">{formatCurrency(stats?.total_spend || '0', currency)}</div>
                </div>
                <div className="kpi-card">
                    <div className="kpi-label">YTD Spend</div>
                    <div className="kpi-value expense">{formatCurrency(stats?.ytd_spend || '0', currency)}</div>
                </div>
            </div>

            {/* Search */}
            <div className="filter-bar">
                <input
                    type="text"
                    className="search-input"
                    placeholder="Search suppliers by name or email..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                />
            </div>

            {/* Main Content */}
            <div className="content-layout">
                {/* Table */}
                <div className="table-container">
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Supplier</th>
                                <th>Contact</th>
                                <th className="text-right">Total Spend</th>
                                <th className="text-right">YTD Spend</th>
                                <th className="text-center">Expenses</th>
                                <th className="text-center">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {suppliers.length === 0 ? (
                                <tr>
                                    <td colSpan={6} className="empty-state">
                                        No suppliers found. <a href="/suppliers/new/">Add your first supplier</a>
                                    </td>
                                </tr>
                            ) : (
                                suppliers.map((supplier) => (
                                    <tr
                                        key={supplier.id}
                                        className={selectedSupplier?.id === supplier.id ? 'selected' : ''}
                                        onClick={() => setSelectedSupplier(supplier)}
                                    >
                                        <td className="supplier-name">{supplier.name}</td>
                                        <td>
                                            <div className="contact-info">
                                                {supplier.email && <span className="email">{supplier.email}</span>}
                                                {supplier.phone && <span className="phone">{supplier.phone}</span>}
                                            </div>
                                        </td>
                                        <td className="text-right expense">
                                            {formatCurrency(supplier.total_spend, currency)}
                                        </td>
                                        <td className="text-right expense">
                                            {formatCurrency(supplier.ytd_spend, currency)}
                                        </td>
                                        <td className="text-center">
                                            <span className="badge">{supplier.expense_count}</span>
                                        </td>
                                        <td className="text-center">
                                            <div className="action-buttons">
                                                <a href={`/suppliers/${supplier.id}/edit/`} className="btn btn-sm btn-secondary">
                                                    Edit
                                                </a>
                                            </div>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>

                {/* Detail Panel */}
                {selectedSupplier && (
                    <div className="detail-panel">
                        <div className="panel-header">
                            <h3>{selectedSupplier.name}</h3>
                            <button className="close-btn" onClick={() => setSelectedSupplier(null)}>×</button>
                        </div>
                        <div className="panel-content">
                            <div className="detail-section">
                                <h4>Contact Information</h4>
                                {selectedSupplier.email && (
                                    <div className="detail-row">
                                        <span className="label">Email</span>
                                        <span className="value">{selectedSupplier.email}</span>
                                    </div>
                                )}
                                {selectedSupplier.phone && (
                                    <div className="detail-row">
                                        <span className="label">Phone</span>
                                        <span className="value">{selectedSupplier.phone}</span>
                                    </div>
                                )}
                                {selectedSupplier.address && (
                                    <div className="detail-row">
                                        <span className="label">Address</span>
                                        <span className="value">{selectedSupplier.address}</span>
                                    </div>
                                )}
                            </div>
                            <div className="detail-section">
                                <h4>Spending Summary</h4>
                                <div className="detail-row">
                                    <span className="label">Total Spend</span>
                                    <span className="value expense">{formatCurrency(selectedSupplier.total_spend, currency)}</span>
                                </div>
                                <div className="detail-row">
                                    <span className="label">YTD Spend</span>
                                    <span className="value expense">{formatCurrency(selectedSupplier.ytd_spend, currency)}</span>
                                </div>
                                <div className="detail-row">
                                    <span className="label">Total Expenses</span>
                                    <span className="value">{selectedSupplier.expense_count}</span>
                                </div>
                            </div>
                            <div className="panel-actions">
                                <a href={`/suppliers/${selectedSupplier.id}/edit/`} className="btn btn-primary btn-block">
                                    Edit Supplier
                                </a>
                                <a href={`/expenses/new/?supplier=${selectedSupplier.id}`} className="btn btn-secondary btn-block">
                                    Add Expense
                                </a>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            <style>{`
        .page-container {
          padding: 24px;
          max-width: 1400px;
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
        .btn {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 10px 18px;
          border-radius: 8px;
          font-weight: 500;
          text-decoration: none;
          cursor: pointer;
          border: none;
          transition: all 0.2s;
        }
        .btn-primary {
          background: linear-gradient(135deg, #8b5cf6, #7c3aed);
          color: white;
        }
        .btn-primary:hover {
          background: linear-gradient(135deg, #7c3aed, #6d28d9);
        }
        .btn-secondary {
          background: #f1f5f9;
          color: #334155;
        }
        .btn-secondary:hover {
          background: #e2e8f0;
        }
        .btn-sm {
          padding: 6px 12px;
          font-size: 13px;
        }
        .btn-block {
          width: 100%;
          justify-content: center;
        }
        .kpi-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
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
        .kpi-value.expense { color: #dc2626; }
        .filter-bar {
          margin-bottom: 20px;
        }
        .search-input {
          width: 100%;
          max-width: 400px;
          padding: 12px 16px;
          border: 1px solid #e2e8f0;
          border-radius: 8px;
          font-size: 14px;
        }
        .search-input:focus {
          outline: none;
          border-color: #8b5cf6;
          box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.1);
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
          background: #f5f3ff;
        }
        .text-right { text-align: right; }
        .text-center { text-align: center; }
        .supplier-name {
          font-weight: 500;
          color: #1e293b;
        }
        .contact-info {
          display: flex;
          flex-direction: column;
          gap: 2px;
          font-size: 13px;
        }
        .contact-info .email { color: #64748b; }
        .contact-info .phone { color: #94a3b8; }
        .expense { color: #dc2626; }
        .badge {
          display: inline-block;
          padding: 4px 12px;
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
        .empty-state a {
          color: #8b5cf6;
          text-decoration: none;
        }
        .detail-panel {
          width: 360px;
          background: white;
          border-radius: 12px;
          box-shadow: 0 1px 3px rgba(0,0,0,0.1);
          overflow: hidden;
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
        }
        .panel-actions {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .loading-spinner, .error-state {
          text-align: center;
          padding: 48px;
          color: #64748b;
        }
        .error-state { color: #dc2626; }
        .action-buttons {
          display: flex;
          gap: 8px;
          justify-content: center;
        }
      `}</style>
        </div>
    );
};

export default SuppliersPage;
