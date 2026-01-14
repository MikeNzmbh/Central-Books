/**
 * Agentic Journal View
 * 
 * Displays journal entries with debit/credit breakdown.
 */

import React from 'react';

interface JournalLine {
    account_code: string;
    account_name: string;
    side: string;
    amount: string | number;
}

interface JournalEntry {
    entry_id: string;
    date: string;
    description: string;
    lines: JournalLine[];
    is_balanced: boolean;
    total_debits: string | number;
    total_credits: string | number;
}

interface Props {
    entries: JournalEntry[];
}

const AgenticJournalView: React.FC<Props> = ({ entries }) => {
    const formatAmount = (amount: string | number) => {
        const num = typeof amount === 'string' ? parseFloat(amount) : amount;
        return `$${num.toFixed(2)}`;
    };

    if (!entries || entries.length === 0) {
        return (
            <div className="journal-view empty">
                <p>No journal entries generated</p>
            </div>
        );
    }

    return (
        <div className="journal-view">
            <div className="journal-summary">
                <span className="entry-count">{entries.length} entries</span>
                <span className="balanced-count">
                    {entries.filter(e => e.is_balanced).length} balanced
                </span>
            </div>

            {entries.map((entry) => (
                <div
                    key={entry.entry_id}
                    className={`journal-entry ${entry.is_balanced ? 'balanced' : 'unbalanced'}`}
                >
                    <div className="entry-header">
                        <div className="entry-title">
                            <span className="entry-id">{entry.entry_id}</span>
                            <span className={`balance-badge ${entry.is_balanced ? 'ok' : 'error'}`}>
                                {entry.is_balanced ? '✓ Balanced' : '✗ Unbalanced'}
                            </span>
                        </div>
                        <div className="entry-meta">
                            <span className="entry-date">{entry.date}</span>
                        </div>
                    </div>

                    <p className="entry-description">{entry.description}</p>

                    <table className="entry-lines">
                        <thead>
                            <tr>
                                <th>Account</th>
                                <th>Debit</th>
                                <th>Credit</th>
                            </tr>
                        </thead>
                        <tbody>
                            {(entry.lines || []).map((line, idx) => (
                                <tr key={idx}>
                                    <td>
                                        <span className="account-code">{line.account_code}</span>
                                        <span className="account-name">{line.account_name}</span>
                                    </td>
                                    <td className="amount debit">
                                        {line.side === 'debit' ? formatAmount(line.amount) : ''}
                                    </td>
                                    <td className="amount credit">
                                        {line.side === 'credit' ? formatAmount(line.amount) : ''}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                        <tfoot>
                            <tr>
                                <td><strong>Total</strong></td>
                                <td className="amount debit">{formatAmount(entry.total_debits)}</td>
                                <td className="amount credit">{formatAmount(entry.total_credits)}</td>
                            </tr>
                        </tfoot>
                    </table>
                </div>
            ))}
        </div>
    );
};

export default AgenticJournalView;
