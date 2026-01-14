# Customer App Architecture

## High-level layout
- `apps/customer/src/main.tsx`: SPA entrypoint, installs shared fetch + renders `App`.
- `apps/customer/src/App.tsx`: routing + auth gates + lazy-loaded route boundaries.
- `apps/customer/src/**/**-entry.tsx`: standalone entrypoints for embedded pages (lists, reports, companion panels).

## Routing & auth
- `AppRoutes` owns all customer routes and wraps protected areas in `RequireAuth`.
- Heavy routes are lazy-loaded with `React.lazy` to keep the initial bundle small.
- Auth routes (`/login`, `/signup`, `/welcome`) remain eagerly loaded.

## Directory map (current)
- `apps/customer/src/companion`: AI companion surfaces (control tower, issues, tax).
- `apps/customer/src/reports`: P&L, cashflow, print views.
- `apps/customer/src/reconciliation`: reconciliation flows + report.
- `apps/customer/src/dashboard`: main customer dashboard.
- `apps/customer/src/invoices`, `apps/customer/src/receipts`, `apps/customer/src/expenses`: transaction surfaces.
- `apps/customer/src/banking`, `apps/customer/src/bankReview`, `apps/customer/src/booksReview`: banking + reviews.
- `apps/customer/src/settings`: account + team settings.
- `apps/customer/src/components`: shared UI (shadcn + bespoke).
- `apps/customer/src/api`: API clients + wrappers.
- `apps/customer/src/utils`: small, pure helpers.
- `apps/customer/src/layouts`, `apps/customer/src/contexts`, `apps/customer/src/hooks`: cross-cutting plumbing.

## Conventions
- Route pages should stay thin and compose feature components.
- Feature code should be colocated with its APIs, types, and subcomponents.
- Keep customer-safe copy rules intact in `apps/customer/src/companion/companionCopy.ts`.
- Avoid pulling heavy dependencies into `App.tsx` unless they are on the critical path.

## Adding a new route
1. Create the page component in the relevant feature directory.
2. Add a lazy import in `apps/customer/src/App.tsx`.
3. Wire the route in `AppRoutes` with a `Suspense` boundary.
4. If the page is large, keep any chart/editor libs behind lazy routes.
