# Customer App Source Guide

## Entry points
- `main.tsx`: SPA bootstrap.
- `App.tsx`: routing + auth + lazy-loaded routes.
- `**/**-entry.tsx`: standalone embedded entrypoints.

## Core directories
- `companion`: AI companion surfaces, control tower, tax.
- `reports`: P&L, cashflow, print surfaces.
- `reconciliation`: reconciliation flows + report.
- `dashboard`: main customer dashboard.
- `banking`, `bankReview`, `booksReview`: banking + review experiences.
- `invoices`, `receipts`, `expenses`, `customers`, `suppliers`, `products`: transactional surfaces.
- `settings`: account + team settings.
- `components`: shared UI primitives.
- `api`, `utils`, `hooks`, `contexts`, `layouts`: shared plumbing.

## Route hygiene
- Keep new routes lazy-loaded in `App.tsx`.
- Avoid importing heavy libraries in the main entrypoint.
