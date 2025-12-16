# Report Print Views Documentation

## Overview

This document describes the universal PDF export functionality for Clover Books reports. All reports use the browser's Print → "Save as PDF" feature, with no backend PDF generation required.

## Architecture

### Components

- **ReportShell** (`reports/ReportShell.tsx`) - Universal report layout component
- **ReportExportButton** (`reports/ReportExportButton.tsx`) - Shared "Download PDF" button
- **Print Preview Components** - Report-specific preview components using ReportShell
- **Print Page Components** - Page wrappers that load data and render previews

### Flow

1. User views a report page (Reconciliation, Cashflow, or P&L)
2. Clicks "Download PDF" button in header
3. Opens print-friendly view in new tab
4. Uses browser Print → "Save as PDF"

---

## Report Types

### 1. Reconciliation Report

**Main Page:** `reconciliation/ReconciliationPage.tsx`  
**Preview Component:** `reconciliation/ReconciliationReportPreview.tsx`  
**Print Page:** `reconciliation/ReconciliationReportPage.tsx`  
**Entry Point:** `reconciliation/reconciliation-report-entry.tsx`

**Route:** `/reconciliation/:sessionId/report/`

**Data Flow:**
- Main page shows export button when a session is active
- Button opens `/reconciliation/{sessionId}/report/` in new tab
- Print page fetches session data via `/api/reconciliation/session/{sessionId}/`
- Renders `ReconciliationReportPreview` with formatted data

**Preview Contents:**
- KPIs: Opening balance, Statement closing, Ledger closing, Difference
- Bank feed summary table (Date, Description, Ref, Amount, Status)
- Reconciliation summary narrative

### 2. Cashflow Report

**Main Page:** `reports/CashflowReportPage.tsx`  
**Preview Component:** `reports/CashflowReportPreview.tsx`  
**Print Page:** `reports/CashflowReportPrintPage.tsx`  
**Entry Point:** `reports/cashflow-report-print-entry.tsx`

**Route:** `/reports/cashflow/print/`

**Data Flow:**
- Main page shows export button in header
- Button opens `/reports/cashflow/print/` in new tab
- Print page receives data via Django template (same as main page)
- Renders `CashflowReportPreview` with formatted data

**Preview Contents:**
- KPIs: Net cash change, Total inflows, Total outflows
- Cash movement trend table (Period, Cash In, Cash Out, Net Change)
- Top cash drivers table (Category, Type, Amount)
- Cashflow summary narrative

### 3. Profit & Loss Report

**Main Page:** _To be determined (P&L page not yet implemented)_  
**Preview Component:** `reports/ProfitAndLossReportPreview.tsx`  
**Print Page:** `reports/ProfitAndLossReportPage.tsx`  
**Entry Point:** `reports/pl-report-entry.tsx`

**Route:** `/reports/pl/print/`

**Data Flow:**
- Main page will show export button in header
- Button will open `/reports/pl/print/` in new tab
- Print page will receive data via Django template
- Renders `ProfitAndLossReportPreview` with formatted data

**Preview Contents:**
- KPIs: Total revenue, Total expenses, Net income
- Revenue breakdown table (Category, Amount)
- Expenses breakdown table (Category, Amount)
- P&L summary narrative

---

## Using ReportExportButton

```tsx
import { ReportExportButton } from "../reports/ReportExportButton";

// Basic usage - opens URL in new tab
<ReportExportButton to="/reconciliation/123/report/" />

// Custom label
<ReportExportButton 
  to="/reports/cashflow/print/" 
  label="Print Cashflow" 
/>

// Custom click handler
<ReportExportButton 
  onClick={() => window.print()} 
  label="Print Page" 
/>

// Disabled state
<Report ExportButton 
  to={reportUrl} 
  disabled={!dataLoaded} 
/>
```

**Props:**
- `to?: string` - URL to navigate to (opens in new tab)
- `onClick?:  () => void` - Custom click handler (alternative to `to`)
- `label?: string` - Button text (default: "Download PDF")
- `className?: string` - Additional CSS classes
- `disabled?: boolean` - Disabled state

---

## Example URLs

### Testing Print Views

**Reconciliation:**
```
http://localhost:8000/reconciliation/SESSION_ID/report/
```
Replace `SESSION_ID` with actual session ID from reconciliation page.

**Cashflow:**
```
http://localhost:8000/reports/cashflow/print/
```
Uses same data as main cashflow page.

**P&L:**
```
http://localhost:8000/reports/pl/print/
```
_Not yet implemented - requires Django backend view_

---

## Backend Requirements

### Django Templates Needed

Each print view requires a Django template that:
1. Includes the appropriate entry point script
2. Provides a root element with correct ID
3. Injects data via JSON script tag (for non-API views)

**Example for Reconciliation:**
```html
<!-- templates/reconciliation_report.html -->
<div id="reconciliation-report-root" data-session-id="{{ session_id }}"></div>
<script type="module" src="{% static 'frontend/reconciliation-report-entry.js' %}"></script>
```

**Example for Cashflow:**
```html
<!-- templates/cashflow_report_print.html -->
<div id="cashflow-report-print-root"></div>
<script id="cashflow-report-print-data" type="application/json">
  {{ report_data|json }}
</script>
<script type="module" src="{% static 'frontend/cashflow-report-print-entry.js' %}"></script>
```

### Django Views Needed

1. **Reconciliation Report View** (`/reconciliation/<session_id>/report/`)
   - Renders `reconciliation_report.html`
   - Passes `session_id` to template

2. **Cashflow Report Print View** (`/reports/cashflow/print/`)
   - Reuses cashflow data loading logic
   - Renders `cashflow_report_print.html`
   - Injects data as JSON

3. **P&L Report Print View** (`/reports/pl/print/`)
   - Loads P&L data for period
   - Renders `pl_report_print.html`
   - Injects data as JSON

---

## Vite Configuration

Entry points added to `vite.config.ts`:

```typescript
{
  'reconciliation-report': '/src/reconciliation/reconciliation-report-entry.tsx',
  'cashflow-report-print': '/src/reports/cashflow-report-print-entry.tsx',
  'pl-report': '/src/reports/pl-report-entry.tsx',
}
```

---

## Print Styling

All print views use:
- White background (`bg-white`)
- Print-safe layout (no sidebar, minimal chrome)
- Floating "Print Report" button (hidden when printing via `print:hidden`)
- Responsive text sizing from ReportShell

**Print CSS:**
```css
@media print {
  .print\:hidden {
    display: none;
  }
  
  .print\:bg-white {
    background-color: white;
  }
}
```

---

## Files Modified/Created

### New Files (10)
1. `reports/ReportExportButton.tsx` - Shared button component
2. `reconciliation/ReconciliationReportPage.tsx` - Reconciliation print page
3. `reconciliation/reconciliation-report-entry.tsx` - Entry point
4. `reports/CashflowReportPreview.tsx` - Cashflow preview component
5. `reports/CashflowReportPrintPage.tsx` - Cashflow print page
6. `reports/cashflow-report-print-entry.tsx` - Entry point
7. `reports/ProfitAndLossReportPreview.tsx` - P&L preview component
8. `reports/ProfitAndLossReportPage.tsx` - P&L print page
9. `reports/pl-report-entry.tsx` - Entry point
10. `docs/reports-print-views.md` - This documentation

### Modified Files (2)
1. `reconciliation/ReconciliationPage.tsx` - Added export button to header
2. `reports/CashflowReportPage.tsx` - Added export button to header

---

## Next Steps (Backend)

To complete the implementation, the following Django work is needed:

1. **Add Vite entry points** to `vite.config.ts`
2. **Create Django templates** for each print view
3. **Create Django URL routes** for print views
4. **Create Django views** to render templates with data
5. **Test print flow** end-to-end for all three reports

---

## Testing Checklist

- [ ] Reconciliation: Export button appears when session is active
- [ ] Reconciliation: Button opens print view in new tab
- [ ] Reconciliation: Print view loads session data correctly
- [ ] Reconciliation: Print view renders all KPIs and tables
- [ ] Reconciliation: Browser print works correctly
- [ ] Cashflow: Export button appears in header
- [ ] Cashflow: Button opens print view in new tab
- [ ] Cashflow: Print view displays correct data
- [ ] Cashflow: Browser print works correctly
- [ ] P&L: Export button appears (once P&L page exists)
- [ ] P&L: Button opens print view in new tab
- [ ] P&L: Print view renders correctly
- [ ] P&L: Browser print works correctly
- [ ] All print views: Responsive on mobile/tablet/desktop
- [ ] All print views: Print button hidden when printing
- [ ] All print views: No console errors

---

## Design Decisions

1. **Browser Print vs Backend PDF:** Using browser print keeps the solution simple, frontend-only, and avoids PDF library dependencies.

2. **New Tab vs Modal:** Opening print views in new tabs allows users to keep their main view open and compare data.

3. **Separate Preview Components:** Each report type has its own preview component for flexibility and maintainability.

4. **Shared ReportShell:** All previews use the same shell for consistent styling and structure.

5. **Django Templates:** Using Django's existing template system for data injection avoids adding React Router complexity.
