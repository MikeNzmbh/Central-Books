import React from 'react';
import { createRoot } from 'react-dom/client';
import { SuppliersPage } from './SuppliersPage';

const container = document.getElementById('suppliers-root');
if (container) {
    const root = createRoot(container);
    root.render(
        <React.StrictMode>
            <SuppliersPage />
        </React.StrictMode>
    );
}
