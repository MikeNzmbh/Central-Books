import React, { useState, useEffect } from 'react';

interface Item {
    id: number;
    name: string;
    sku: string;
    type: string;
    price: string;
    description: string;
    is_archived: boolean;
    income_category_id: number | null;
    income_category_name: string | null;
}

interface Stats {
    active_count: number;
    product_count: number;
    service_count: number;
}

interface TypeChoice {
    value: string;
    label: string;
}

interface ProductData {
    items: Item[];
    stats: Stats;
    currency: string;
    type_choices: TypeChoice[];
}

const formatCurrency = (value: string, currency: string): string => {
    const num = parseFloat(value) || 0;
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: currency || 'USD',
    }).format(num);
};

export const ProductsPage: React.FC = () => {
    const [data, setData] = useState<ProductData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [kindFilter, setKindFilter] = useState('all');
    const [statusFilter, setStatusFilter] = useState('active');
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedItem, setSelectedItem] = useState<Item | null>(null);

    const fetchData = async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            if (kindFilter !== 'all') params.set('kind', kindFilter);
            if (statusFilter !== 'all') params.set('status', statusFilter);
            if (searchQuery) params.set('q', searchQuery);
            const response = await fetch(`/api/products/list/?${params.toString()}`);
            if (!response.ok) throw new Error('Failed to fetch products');
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
    }, [kindFilter, statusFilter]);

    useEffect(() => {
        const debounce = setTimeout(() => {
            fetchData();
        }, 300);
        return () => clearTimeout(debounce);
    }, [searchQuery]);

    if (loading && !data) {
        return (
            <div className="page-container">
                <div className="loading-spinner">Loading products & services...</div>
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
    const items = data?.items || [];

    return (
        <div className="page-container">
            {/* Header */}
            <div className="page-header">
                <div className="header-content">
                    <h1>Products & Services</h1>
                    <a href="/items/new/" className="btn btn-primary">
                        <span className="icon">+</span> New Item
                    </a>
                </div>
            </div>

            {/* KPI Cards */}
            <div className="kpi-grid">
                <div className="kpi-card">
                    <div className="kpi-label">Active Items</div>
                    <div className="kpi-value">{stats?.active_count || 0}</div>
                </div>
                <div className="kpi-card">
                    <div className="kpi-label">Products</div>
                    <div className="kpi-value product">{stats?.product_count || 0}</div>
                    <div className="kpi-icon">📦</div>
                </div>
                <div className="kpi-card">
                    <div className="kpi-label">Services</div>
                    <div className="kpi-value service">{stats?.service_count || 0}</div>
                    <div className="kpi-icon">⚙️</div>
                </div>
            </div>

            {/* Filters */}
            <div className="filter-bar">
                <input
                    type="text"
                    className="search-input"
                    placeholder="Search by name or SKU..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                />
                <div className="filter-group">
                    <select
                        className="filter-select"
                        value={kindFilter}
                        onChange={(e) => setKindFilter(e.target.value)}
                    >
                        <option value="all">All Types</option>
                        <option value="product">Products</option>
                        <option value="service">Services</option>
                    </select>
                    <select
                        className="filter-select"
                        value={statusFilter}
                        onChange={(e) => setStatusFilter(e.target.value)}
                    >
                        <option value="active">Active</option>
                        <option value="archived">Archived</option>
                        <option value="all">All Status</option>
                    </select>
                </div>
            </div>

            {/* Main Content */}
            <div className="content-layout">
                {/* Table */}
                <div className="table-container">
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>SKU</th>
                                <th>Type</th>
                                <th className="text-right">Price</th>
                                <th>Category</th>
                                <th className="text-center">Status</th>
                                <th className="text-center">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {items.length === 0 ? (
                                <tr>
                                    <td colSpan={7} className="empty-state">
                                        No items found. <a href="/items/new/">Add your first product or service</a>
                                    </td>
                                </tr>
                            ) : (
                                items.map((item) => (
                                    <tr
                                        key={item.id}
                                        className={`${item.is_archived ? 'archived' : ''} ${selectedItem?.id === item.id ? 'selected' : ''}`}
                                        onClick={() => setSelectedItem(item)}
                                    >
                                        <td className="item-name">
                                            <span className="type-icon">{item.type === 'PRODUCT' ? '📦' : '⚙️'}</span>
                                            {item.name}
                                        </td>
                                        <td className="sku">{item.sku || '-'}</td>
                                        <td>
                                            <span className={`type-badge ${item.type.toLowerCase()}`}>
                                                {item.type === 'PRODUCT' ? 'Product' : 'Service'}
                                            </span>
                                        </td>
                                        <td className="text-right price">
                                            {formatCurrency(item.price, currency)}
                                        </td>
                                        <td className="category">
                                            {item.income_category_name || '-'}
                                        </td>
                                        <td className="text-center">
                                            <span className={`status-badge ${item.is_archived ? 'archived' : 'active'}`}>
                                                {item.is_archived ? 'Archived' : 'Active'}
                                            </span>
                                        </td>
                                        <td className="text-center">
                                            <div className="action-buttons">
                                                <a href={`/items/${item.id}/edit/`} className="btn btn-sm btn-secondary">
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
                {selectedItem && (
                    <div className="detail-panel">
                        <div className="panel-header">
                            <div className="header-with-icon">
                                <span className="type-icon-large">{selectedItem.type === 'PRODUCT' ? '📦' : '⚙️'}</span>
                                <h3>{selectedItem.name}</h3>
                            </div>
                            <button className="close-btn" onClick={() => setSelectedItem(null)}>×</button>
                        </div>
                        <div className="panel-content">
                            <div className="detail-section">
                                <h4>Item Details</h4>
                                <div className="detail-row">
                                    <span className="label">Type</span>
                                    <span className={`value type-badge ${selectedItem.type.toLowerCase()}`}>
                                        {selectedItem.type === 'PRODUCT' ? 'Product' : 'Service'}
                                    </span>
                                </div>
                                {selectedItem.sku && (
                                    <div className="detail-row">
                                        <span className="label">SKU</span>
                                        <span className="value">{selectedItem.sku}</span>
                                    </div>
                                )}
                                <div className="detail-row">
                                    <span className="label">Price</span>
                                    <span className="value price">{formatCurrency(selectedItem.price, currency)}</span>
                                </div>
                                <div className="detail-row">
                                    <span className="label">Status</span>
                                    <span className={`value ${selectedItem.is_archived ? 'archived' : 'active'}`}>
                                        {selectedItem.is_archived ? 'Archived' : 'Active'}
                                    </span>
                                </div>
                            </div>
                            {selectedItem.income_category_name && (
                                <div className="detail-section">
                                    <h4>Accounting</h4>
                                    <div className="detail-row">
                                        <span className="label">Income Category</span>
                                        <span className="value">{selectedItem.income_category_name}</span>
                                    </div>
                                </div>
                            )}
                            {selectedItem.description && (
                                <div className="detail-section">
                                    <h4>Description</h4>
                                    <p className="description-text">{selectedItem.description}</p>
                                </div>
                            )}
                            <div className="panel-actions">
                                <a href={`/items/${selectedItem.id}/edit/`} className="btn btn-primary btn-block">
                                    Edit Item
                                </a>
                                <a href={`/invoices/new/?item=${selectedItem.id}`} className="btn btn-secondary btn-block">
                                    Add to Invoice
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
          background: linear-gradient(135deg, #f59e0b, #d97706);
          color: white;
        }
        .btn-primary:hover {
          background: linear-gradient(135deg, #d97706, #b45309);
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
          position: relative;
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
        .kpi-value.product { color: #0ea5e9; }
        .kpi-value.service { color: #8b5cf6; }
        .kpi-icon {
          position: absolute;
          right: 20px;
          top: 50%;
          transform: translateY(-50%);
          font-size: 32px;
          opacity: 0.3;
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
          border-color: #f59e0b;
          box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.1);
        }
        .filter-select {
          padding: 10px 14px;
          border: 1px solid #e2e8f0;
          border-radius: 8px;
          font-size: 14px;
          background: white;
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
          background: #fffbeb;
        }
        .data-table tbody tr.archived {
          opacity: 0.6;
        }
        .text-right { text-align: right; }
        .text-center { text-align: center; }
        .item-name {
          font-weight: 500;
          color: #1e293b;
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .type-icon {
          font-size: 16px;
        }
        .type-icon-large {
          font-size: 24px;
        }
        .sku {
          font-family: monospace;
          color: #64748b;
        }
        .type-badge {
          display: inline-block;
          padding: 4px 10px;
          border-radius: 12px;
          font-size: 12px;
          font-weight: 500;
        }
        .type-badge.product {
          background: #e0f2fe;
          color: #0369a1;
        }
        .type-badge.service {
          background: #ede9fe;
          color: #6d28d9;
        }
        .price {
          font-weight: 600;
          color: #059669;
        }
        .category {
          color: #64748b;
        }
        .status-badge {
          display: inline-block;
          padding: 4px 10px;
          border-radius: 12px;
          font-size: 12px;
          font-weight: 500;
        }
        .status-badge.active {
          background: #dcfce7;
          color: #16a34a;
        }
        .status-badge.archived {
          background: #fef3c7;
          color: #92400e;
        }
        .empty-state {
          text-align: center;
          padding: 48px;
          color: #64748b;
        }
        .empty-state a {
          color: #f59e0b;
          text-decoration: none;
        }
        .detail-panel {
          width: 360px;
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
        .header-with-icon {
          display: flex;
          align-items: center;
          gap: 10px;
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
        .value.archived { color: #f59e0b; }
        .value.active { color: #059669; }
        .description-text {
          margin: 0;
          font-size: 14px;
          color: #475569;
          line-height: 1.5;
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

export default ProductsPage;
