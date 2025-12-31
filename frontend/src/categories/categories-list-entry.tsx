import React from 'react';
import { createRoot } from 'react-dom/client';
import CategoriesPage from './CategoriesPage';
import "../setup";

const container = document.getElementById('categories-root');
if (container) {
    const root = createRoot(container);
    root.render(
        <React.StrictMode>
            <CategoriesPage />
        </React.StrictMode>
    );
}
