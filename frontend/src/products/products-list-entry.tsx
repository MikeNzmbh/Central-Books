import React from 'react';
import { createRoot } from 'react-dom/client';
import { ProductsPage } from './ProductsPage';

const container = document.getElementById('products-root');
if (container) {
    const root = createRoot(container);
    root.render(
        <React.StrictMode>
            <ProductsPage />
        </React.StrictMode>
    );
}
