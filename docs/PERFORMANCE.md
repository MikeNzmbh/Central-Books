# Customer App Performance

## Goals
- Keep initial JS small and defer heavy pages with route-level code splitting.
- Avoid pulling large libraries (charts, editors) into the main bundle.
- Maintain customer-visible behavior and copy while optimizing load time.

## Bundle analyzer
Run from `apps/customer`:

```bash
BUNDLE_REPORT="/Users/wherethefuckthefunction/Desktop/Project Clover/docs/perf/bundle-report.before.html" npm run build -- --mode analyze
BUNDLE_REPORT="/Users/wherethefuckthefunction/Desktop/Project Clover/docs/perf/bundle-report.after.html" npm run build -- --mode analyze
```

Build output logs:
- `docs/perf/customer-build.before.txt`
- `docs/perf/customer-build.after.txt`

## Code-splitting rules
- Route pages should be imported with `React.lazy` in `apps/customer/src/App.tsx`.
- Only keep login/signup/welcome + dashboard eagerly loaded unless a route is on the critical path.
- Keep chart-heavy pages (companion control tower, reports, reconciliation) behind lazy routes.

## Quick checks before merging
- `npm run build` in `apps/customer` and review chunk sizes.
- `npm test` in `apps/customer`.
- Confirm the main chunk stays under 500 kB gzip when feasible.
