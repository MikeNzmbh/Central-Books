/**
 * Agentic Console Entry Point (Vite)
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import AgenticConsolePage from './AgenticConsolePage';
import './AgenticConsole.css';

const root = document.getElementById('agentic-console-root');
if (root) {
    ReactDOM.createRoot(root).render(
        <React.StrictMode>
            <AgenticConsolePage />
        </React.StrictMode>
    );
}
