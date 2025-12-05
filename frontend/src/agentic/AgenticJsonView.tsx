/**
 * Agentic JSON View
 * 
 * Raw JSON viewer for workflow output.
 */

import React, { useState } from 'react';

interface Props {
    data: any;
}

const AgenticJsonView: React.FC<Props> = ({ data }) => {
    const [expanded, setExpanded] = useState(true);
    const [copied, setCopied] = useState(false);

    const jsonString = JSON.stringify(data, null, 2);

    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(jsonString);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch (err) {
            console.error('Failed to copy:', err);
        }
    };

    return (
        <div className="json-view">
            <div className="json-toolbar">
                <button
                    className="toggle-btn"
                    onClick={() => setExpanded(!expanded)}
                >
                    {expanded ? '⊟ Collapse' : '⊞ Expand'}
                </button>
                <button
                    className="copy-btn"
                    onClick={handleCopy}
                >
                    {copied ? '✓ Copied!' : '⎘ Copy'}
                </button>
            </div>

            <pre className={`json-content ${expanded ? 'expanded' : 'collapsed'}`}>
                <code>{jsonString}</code>
            </pre>
        </div>
    );
};

export default AgenticJsonView;
