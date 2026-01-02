import React, { useEffect, useState } from "react";
import {
    fetchWorkspace360,
    type Workspace360,
} from "./api";
import { Card, SimpleTable, StatusPill, cn } from "./AdminUI";

interface Workspace360SectionProps {
    workspaceId: number;
    workspaceName?: string;
}

/**
 * Workspace 360 "God View" - Unified observability panel
 * Aligned with Gemini spec's Customer 360 dashboard concept
 */
export const Workspace360Section: React.FC<Workspace360SectionProps> = ({
    workspaceId,
    workspaceName,
}) => {
    const [data, setData] = useState<Workspace360 | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        setError(null);

        fetchWorkspace360(workspaceId)
            .then((result) => {
                if (!cancelled) {
                    setData(result);
                }
            })
            .catch((err) => {
                if (!cancelled) {
                    setError(err.message || "Failed to load workspace data");
                }
            })
            .finally(() => {
                if (!cancelled) {
                    setLoading(false);
                }
            });

        return () => {
            cancelled = true;
        };
    }, [workspaceId]);

    if (loading) {
        return (
            <div className="space-y-4">
                <h2 className="text-lg font-semibold text-slate-900">
                    Workspace 360: {workspaceName || `#${workspaceId}`}
                </h2>
                <p className="text-sm text-slate-500">Loading workspace data...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="space-y-4">
                <h2 className="text-lg font-semibold text-slate-900">
                    Workspace 360: {workspaceName || `#${workspaceId}`}
                </h2>
                <p className="text-sm text-red-600">Error: {error}</p>
            </div>
        );
    }

    if (!data) return null;

    return (
        <div className="space-y-6">
            <header>
                <h2 className="text-lg font-semibold text-slate-900">
                    Workspace 360: {data.workspace.name}
                </h2>
                <p className="text-sm text-slate-600">
                    Unified view • Created {data.workspace.created_at ? new Date(data.workspace.created_at).toLocaleDateString() : "Unknown"}
                </p>
            </header>

            {/* Summary Cards */}
            <div className="grid gap-4 lg:grid-cols-4">
                <Card title="Owner" subtitle={data.owner.email || "Unknown"}>
                    <p className="text-sm text-slate-700">{data.owner.full_name || "—"}</p>
                    {data.plan && (
                        <div className="mt-2">
                            <StatusPill tone="neutral" label={data.plan} />
                        </div>
                    )}
                </Card>

                <Card title="Banking" subtitle={`${data.banking.account_count} accounts`}>
                    <div className="space-y-1 text-sm">
                        <p className="text-slate-700">
                            <span className="font-medium text-amber-600">{data.banking.unreconciled_count}</span> unreconciled
                        </p>
                    </div>
                </Card>

                <Card title="Ledger Health" subtitle={`${data.ledger_health.total_accounts} accounts`}>
                    <div className="space-y-1 text-sm">
                        {data.ledger_health.unbalanced_entries > 0 ? (
                            <StatusPill tone="bad" label={`${data.ledger_health.unbalanced_entries} unbalanced`} />
                        ) : (
                            <StatusPill tone="good" label="Balanced" />
                        )}
                        <p className="text-slate-600">{data.ledger_health.total_entries} entries</p>
                    </div>
                </Card>

                <Card title="Tax Guardian" subtitle={data.tax.has_tax_guardian ? "Active" : "Not configured"}>
                    {data.tax.last_period ? (
                        <p className="text-sm text-slate-700">
                            Last: {data.tax.last_period.start_date} – {data.tax.last_period.end_date}
                        </p>
                    ) : (
                        <p className="text-sm text-slate-500">No tax periods</p>
                    )}
                </Card>
            </div>

            {/* Detail Cards */}
            <div className="grid gap-4 lg:grid-cols-2">
                <Card title="Invoices" subtitle="Status breakdown">
                    <div className="grid grid-cols-4 gap-2 text-center text-sm">
                        <div>
                            <p className="text-2xl font-bold text-slate-900">{data.invoices.total}</p>
                            <p className="text-slate-500">Total</p>
                        </div>
                        <div>
                            <p className="text-2xl font-bold text-slate-400">{data.invoices.draft}</p>
                            <p className="text-slate-500">Draft</p>
                        </div>
                        <div>
                            <p className="text-2xl font-bold text-blue-600">{data.invoices.sent}</p>
                            <p className="text-slate-500">Sent</p>
                        </div>
                        <div>
                            <p className="text-2xl font-bold text-emerald-600">{data.invoices.paid}</p>
                            <p className="text-slate-500">Paid</p>
                        </div>
                    </div>
                </Card>

                <Card title="Expenses" subtitle={`${data.expenses.total} total`}>
                    <div className="grid grid-cols-2 gap-2 text-center text-sm">
                        <div>
                            <p className="text-2xl font-bold text-slate-900">
                                ${data.expenses.total_amount.toLocaleString()}
                            </p>
                            <p className="text-slate-500">Total Amount</p>
                        </div>
                        <div>
                            <p className="text-2xl font-bold text-amber-600">{data.expenses.uncategorized}</p>
                            <p className="text-slate-500">Uncategorized</p>
                        </div>
                    </div>
                </Card>
            </div>

            {/* Bank Accounts Table */}
            {data.banking.accounts.length > 0 && (
                <Card title="Bank Accounts" subtitle="Recent accounts">
                    <SimpleTable
                        headers={["Name", "Bank", "Status", "Last Import"]}
                        rows={data.banking.accounts.map((acc) => [
                            acc.name,
                            acc.bank_name,
                            acc.is_active ? (
                                <StatusPill tone="good" label="Active" />
                            ) : (
                                <StatusPill tone="bad" label="Inactive" />
                            ),
                            acc.last_imported_at
                                ? new Date(acc.last_imported_at).toLocaleDateString()
                                : "Never",
                        ])}
                    />
                </Card>
            )}

            {/* Tax Anomalies */}
            {data.tax.has_tax_guardian && (
                <Card title="Tax Anomalies" subtitle="Open issues">
                    <div className="flex gap-4 text-sm">
                        <div className="flex items-center gap-2">
                            <span className="inline-block w-3 h-3 rounded-full bg-red-500"></span>
                            <span>High: {data.tax.open_anomalies.high}</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="inline-block w-3 h-3 rounded-full bg-amber-500"></span>
                            <span>Medium: {data.tax.open_anomalies.medium}</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="inline-block w-3 h-3 rounded-full bg-slate-400"></span>
                            <span>Low: {data.tax.open_anomalies.low}</span>
                        </div>
                    </div>
                </Card>
            )}
        </div>
    );
};

export default Workspace360Section;
