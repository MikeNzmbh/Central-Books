import React from 'react';
import { createRoot } from 'react-dom/client';
import CustomersPage from './CustomersPage';

const container = document.getElementById('customers-root');
if (container) {
    const root = createRoot(container);
    root.render(
        <React.StrictMode>
            <CustomersPage />
        </React.StrictMode>
    );
}
