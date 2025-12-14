import React, { useState, useEffect } from 'react';

interface Category {
    id: number;
    name: string;
    type: string;
    is_archived: boolean;
    expense_count: number;
    total_amount: string;
}

interface Stats {
    total_categories: number;
    expense_categories: number;
    income_categories: number;
}

interface TypeChoice {
    value: string;
    label: string;
}

interface CategoryData {
    categories: Category[];
    stats: Stats;
    type_choices: TypeChoice[];
}

const formatCurrency = (value: string, currency: string = 'USD'): string => {
    const num = parseFloat(value) || 0;
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: currency,
    }).format(num);
};

export const CategoriesPage: React.FC = () => {
    const [data, setData] = useState<CategoryData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [typeFilter, setTypeFilter] = useState('all');
    const [showArchived, setShowArchived] = useState(false);
    const [selectedCategory, setSelectedCategory] = useState<Category | null>(null);

    const fetchData = async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            if (typeFilter !== 'all') params.set('type', typeFilter);
            if (showArchived) params.set('archived', 'true');
            const response = await fetch(`/api/categories/list/?${params.toString()}`);
            if (!response.ok) throw new Error('Failed to fetch categories');
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
    }, [typeFilter, showArchived]);

    if (loading && !data) {
        return (
            <div className="page-container">
                <div className="loading-spinner">Loading categories...</div>
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

    const stats = data?.stats;
    const categories = data?.categories || [];
    const expenseCategories = categories.filter(c => c.type === 'EXPENSE');
    const incomeCategories = categories.filter(c => c.type === 'INCOME');

    return (
        <div className="page-container">
            {/* Header */}
            <div className="page-header">
                <div className="header-content">
                    <h1>Categories</h1>
                    <a href="/categories/new/" className="btn btn-primary">
                        <span className="icon">+</span> New Category
                    </a>
                </div>
            </div>

            {/* KPI Cards */}
            <div className="kpi-grid">
                <div className="kpi-card">
                    <div className="kpi-label">Total Categories</div>
                    <div className="kpi-value">{stats?.total_categories || 0}</div>
                </div>
                <div className="kpi-card">
                    <div className="kpi-label">Expense Categories</div>
                    <div className="kpi-value expense">{stats?.expense_categories || 0}</div>
                </div>
                <div className="kpi-card">
                    <div className="kpi-label">Income Categories</div>
                    <div className="kpi-value income">{stats?.income_categories || 0}</div>
                </div>
            </div>

            {/* Filters */}
            <div className="filter-bar">
                <div className="filter-group">
                    <select
                        className="filter-select"
                        value={typeFilter}
                        onChange={(e) => setTypeFilter(e.target.value)}
                    >
                        <option value="all">All Types</option>
                        <option value="expense">Expense</option>
                        <option value="income">Income</option>
                    </select>
                    <label className="checkbox-label">
                        <input
                            type="checkbox"
                            checked={showArchived}
                            onChange={(e) => setShowArchived(e.target.checked)}
                        />
                        Show Archived
                    </label>
                </div>
            </div>

            {/* Main Content */}
            <div className="content-layout">
                {/* Categories Grid */}
                <div className="categories-container">
                    {/* Expense Categories */}
                    {(typeFilter === 'all' || typeFilter === 'expense') && expenseCategories.length > 0 && (
                        <div className="category-section">
                            <h2 className="section-title expense">
                                <span className="icon">📤</span> Expense Categories
                            </h2>
                            <div className="category-grid">
                                {expenseCategories.map((category) => (
                                    <div
                                        key={category.id}
                                        className={`category-card ${category.is_archived ? 'archived' : ''} ${selectedCategory?.id === category.id ? 'selected' : ''}`}
                                        onClick={() => setSelectedCategory(category)}
                                    >
                                        <div className="card-header">
                                            <span className="category-name">{category.name}</span>
                                            {category.is_archived && <span className="archived-badge">Archived</span>}
                                        </div>
                                        <div className="card-stats">
                                            <div className="stat">
                                                <span className="stat-value">{category.expense_count}</span>
                                                <span className="stat-label">Expenses</span>
                                            </div>
                                            <div className="stat">
                                                <span className="stat-value expense">{formatCurrency(category.total_amount)}</span>
                                                <span className="stat-label">Total</span>
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Income Categories */}
                    {(typeFilter === 'all' || typeFilter === 'income') && incomeCategories.length > 0 && (
                        <div className="category-section">
                            <h2 className="section-title income">
                                <span className="icon">📥</span> Income Categories
                            </h2>
                            <div className="category-grid">
                                {incomeCategories.map((category) => (
                                    <div
                                        key={category.id}
                                        className={`category-card ${category.is_archived ? 'archived' : ''} ${selectedCategory?.id === category.id ? 'selected' : ''}`}
                                        onClick={() => setSelectedCategory(category)}
                                    >
                                        <div className="card-header">
                                            <span className="category-name">{category.name}</span>
                                            {category.is_archived && <span className="archived-badge">Archived</span>}
                                        </div>
                                        <div className="card-stats">
                                            <div className="stat">
                                                <span className="stat-label">Income category for products/services</span>
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {categories.length === 0 && (
                        <div className="empty-state-container">
                            <div className="empty-state">
                                No categories found. <a href="/categories/new/">Create your first category</a>
                            </div>
                        </div>
                    )}
                </div>

                {/* Detail Panel */}
                {selectedCategory && (
                    <div className="detail-panel">
                        <div className="panel-header">
                            <h3>{selectedCategory.name}</h3>
                            <button className="close-btn" onClick={() => setSelectedCategory(null)}>×</button>
                        </div>
                        <div className="panel-content">
                            <div className="detail-section">
                                <h4>Category Details</h4>
                                <div className="detail-row">
                                    <span className="label">Type</span>
                                    <span className={`value type-badge ${selectedCategory.type.toLowerCase()}`}>
                                        {selectedCategory.type === 'EXPENSE' ? '📤 Expense' : '📥 Income'}
                                    </span>
                                </div>
                                <div className="detail-row">
                                    <span className="label">Status</span>
                                    <span className={`value ${selectedCategory.is_archived ? 'archived' : 'active'}`}>
                                        {selectedCategory.is_archived ? 'Archived' : 'Active'}
                                    </span>
                                </div>
                            </div>
                            {selectedCategory.type === 'EXPENSE' && (
                                <div className="detail-section">
                                    <h4>Usage Statistics</h4>
                                    <div className="detail-row">
                                        <span className="label">Expenses</span>
                                        <span className="value">{selectedCategory.expense_count}</span>
                                    </div>
                                    <div className="detail-row">
                                        <span className="label">Total Amount</span>
                                        <span className="value expense">{formatCurrency(selectedCategory.total_amount)}</span>
                                    </div>
                                </div>
                            )}
                            <div className="panel-actions">
                                <a href={`/categories/${selectedCategory.id}/edit/`} className="btn btn-primary btn-block">
                                    Edit Category
                                </a>
                                {selectedCategory.is_archived ? (
                                    <a href={`/categories/${selectedCategory.id}/restore/`} className="btn btn-secondary btn-block">
                                        Restore Category
                                    </a>
                                ) : (
                                    <a href={`/categories/${selectedCategory.id}/archive/`} className="btn btn-secondary btn-block">
                                        Archive Category
                                    </a>
                                )}
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
          background: linear-gradient(135deg, #10b981, #059669);
          color: white;
        }
        .btn-primary:hover {
          background: linear-gradient(135deg, #059669, #047857);
        }
        .btn-secondary {
          background: #f1f5f9;
          color: #334155;
        }
        .btn-secondary:hover {
          background: #e2e8f0;
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
        .kpi-value.income { color: #059669; }
        .filter-bar {
          margin-bottom: 20px;
        }
        .filter-group {
          display: flex;
          gap: 16px;
          align-items: center;
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
        .categories-container {
          flex: 1;
        }
        .category-section {
          margin-bottom: 32px;
        }
        .section-title {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 18px;
          font-weight: 600;
          margin-bottom: 16px;
        }
        .section-title.expense { color: #dc2626; }
        .section-title.income { color: #059669; }
        .section-title .icon { font-size: 20px; }
        .category-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
          gap: 16px;
        }
        .category-card {
          background: white;
          border-radius: 12px;
          padding: 16px;
          box-shadow: 0 1px 3px rgba(0,0,0,0.1);
          cursor: pointer;
          transition: all 0.2s;
          border: 2px solid transparent;
        }
        .category-card:hover {
          box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        .category-card.selected {
          border-color: #10b981;
        }
        .category-card.archived {
          opacity: 0.7;
        }
        .card-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
        }
        .category-name {
          font-weight: 600;
          font-size: 16px;
        }
        .archived-badge {
          font-size: 11px;
          padding: 2px 8px;
          background: #fef3c7;
          color: #92400e;
          border-radius: 10px;
        }
        .card-stats {
          display: flex;
          gap: 24px;
        }
        .stat {
          display: flex;
          flex-direction: column;
        }
        .stat-value {
          font-weight: 600;
          font-size: 18px;
        }
        .stat-value.expense { color: #dc2626; }
        .stat-label {
          font-size: 12px;
          color: #64748b;
        }
        .empty-state-container {
          background: white;
          border-radius: 12px;
          padding: 48px;
          text-align: center;
        }
        .empty-state {
          color: #64748b;
        }
        .empty-state a {
          color: #10b981;
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
        .type-badge.expense { color: #dc2626; }
        .type-badge.income { color: #059669; }
        .value.archived { color: #f59e0b; }
        .value.active { color: #059669; }
        .expense { color: #dc2626; }
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
      `}</style>
        </div>
    );
};

export default CategoriesPage;
