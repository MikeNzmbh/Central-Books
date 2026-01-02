---
description: Apply MiniBooks typography pattern - JetBrains Mono for numbers, SF Pro for text
---

# MiniBooks Typography Pattern

This skill applies the standard MiniBooks typography: **JetBrains Mono** for numeric/currency data, **SF Pro** (system font) for all other text.

## Prerequisites

The following are already set up in the codebase:
- `@fontsource/jetbrains-mono` is installed
- `.font-mono-soft` utility class is defined in `frontend/src/index.css`
- Tailwind's `font-sans` uses the Apple/SF Pro system font stack

## How to Apply to a Page

### 1. Page-Level Font (Optional)

If you want the entire page in JetBrains Mono with exceptions for specific sections:

```tsx
<div className="min-h-screen font-mono-soft">
  {/* Content uses JetBrains Mono by default */}
  
  {/* Override specific sections back to SF Pro */}
  <div className="font-sans">
    {/* Text content stays in SF Pro */}
  </div>
</div>
```

### 2. Numbers-Only Pattern (Recommended)

Keep page in SF Pro, apply JetBrains Mono only to numeric values:

```tsx
{/* Text labels - no special class needed (uses SF Pro) */}
<p className="text-xs text-slate-500">Cash on hand</p>

{/* Currency/numeric values - add font-mono-soft */}
<p className="text-xl font-semibold text-slate-900 font-mono-soft">
  {formatMoney(value)}
</p>

{/* Mixed text with numbers - wrap only the number */}
<p className="text-[11px] text-slate-500">
  <span className="font-mono-soft">{count}</span> invoices
</p>
```

### 3. Percentage Values

```tsx
<span className="font-mono-soft">{percentage.toFixed(1)}%</span> margin
```

### 4. Title with Grey/Black Pattern

Use this for page headings with accent underline:

```tsx
<h1 className="text-3xl font-semibold text-slate-900">
  Morning, {userName}.<br className="hidden md:block" />
  <span className="text-slate-400">Your books are </span>
  <span className="mb-accent-underline">in good shape.</span>
</h1>
```

### 5. Companion Panels (Keep in SF Pro)

If a page uses `font-mono-soft` at the root, override the Companion panel:

```tsx
<div className="... font-sans">
  {/* AI Companion content stays in SF Pro */}
</div>
```

## CSS Classes Reference

| Class | Font | Use For |
|-------|------|---------|
| `font-mono-soft` | JetBrains Mono | Currency amounts, counts, percentages |
| `font-sans` | SF Pro (system) | Labels, descriptions, headings |
| `mb-accent-underline` | N/A | Orange underline decoration |

## Example: Dashboard KPI Card

```tsx
<div className="rounded-3xl border border-slate-100 bg-white/90 px-4 py-4 shadow-sm">
  <p className="text-xs font-medium text-slate-500">Open invoices</p>
  <p className="mt-2 text-xl font-semibold text-slate-900 font-mono-soft">
    {formatMoney(metrics?.open_invoices_total)}
  </p>
  <p className="mt-0.5 text-[11px] text-slate-500">
    <span className="font-mono-soft">{metrics?.open_invoices_count || 0}</span> awaiting payment
  </p>
</div>
```

## Files Using This Pattern

- `frontend/src/dashboard/CloverBooksDashboard.tsx`
- `frontend/src/dashboard/PLSnapshotCard.tsx`
- `frontend/src/dashboard/SuppliersDonutCard.tsx`
- `frontend/src/companion/TaxGuardianPage.tsx`
- `frontend/src/reports/CashflowReportPage.tsx`
