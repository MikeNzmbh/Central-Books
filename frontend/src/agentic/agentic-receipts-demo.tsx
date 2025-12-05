import React from 'react';
import ReactDOM from 'react-dom/client';
import ReceiptsDemoPage from './ReceiptsDemoPage';
import '../index.css';

const rootElement = document.getElementById('agentic-receipts-root');
if (rootElement) {
    ReactDOM.createRoot(rootElement).render(
        <React.StrictMode>
            <ReceiptsDemoPage />
        </React.StrictMode>
    );
}
