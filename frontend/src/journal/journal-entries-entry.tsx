import React from 'react';
import { createRoot } from 'react-dom/client';
import { JournalEntriesPage } from './JournalEntriesPage';

const container = document.getElementById('journal-entries-root');
if (container) {
    const root = createRoot(container);
    root.render(
        <React.StrictMode>
            <JournalEntriesPage />
        </React.StrictMode>
    );
}
