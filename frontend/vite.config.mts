/// <reference types="vitest" />
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  root: path.resolve(__dirname, "src"),
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  build: {
    outDir: path.resolve(__dirname, "static/frontend"),
    emptyOutDir: false,
    manifest: true,
    rollupOptions: {
      input: {
        "bank-feed": path.resolve(__dirname, "src/bank-feed.tsx"),
        "banking-accounts-feed": path.resolve(
          __dirname,
          "src/banking-accounts-feed.tsx"
        ),
        "chart-of-accounts": path.resolve(
          __dirname,
          "src/chart-of-accounts.tsx"
        ),
        "coa-account-detail": path.resolve(
          __dirname,
          "src/coa-account-detail.tsx"
        ),
        dashboard: path.resolve(
          __dirname,
          "src/dashboard/dashboard-entry.tsx"
        ),
        login: path.resolve(__dirname, "src/auth/login-entry.tsx"),
        signup: path.resolve(__dirname, "src/auth/signup-entry.tsx"),
        "account-settings": path.resolve(
          __dirname,
          "src/settings/account-settings-entry.tsx"
        ),
        "workspace-home": path.resolve(
          __dirname,
          "src/pages/workspace-home-entry.tsx"
        ),
        "companion-strip": path.resolve(
          __dirname,
          "src/companion/companion-strip-entry.tsx"
        ),
        "cashflow-report": path.resolve(
          __dirname,
          "src/reports/cashflow-report-entry.tsx"
        ),
        "bank-setup": path.resolve(
          __dirname,
          "src/banking/bank-setup-entry.tsx"
        ),
        reconciliation: path.resolve(
          __dirname,
          "src/reconciliation/reconciliation-entry.tsx"
        ),
        "reconciliation-report": path.resolve(
          __dirname,
          "src/reconciliation/reconciliation-report-entry.tsx"
        ),
        "cashflow-report-print": path.resolve(
          __dirname,
          "src/reports/cashflow-report-print-entry.tsx"
        ),
        "pl-report-print": path.resolve(
          __dirname,
          "src/reports/pl-report-entry.tsx"
        ),
        admin: path.resolve(__dirname, "src/admin.tsx"),
        "agentic-receipts-demo": path.resolve(
          __dirname,
          "src/agentic/agentic-receipts-demo.tsx"
        ),
        receipts: path.resolve(__dirname, "src/receipts/receipts-entry.tsx"),
        invoices: path.resolve(__dirname, "src/invoices/invoices-entry.tsx"),
        "books-review": path.resolve(__dirname, "src/booksReview/books-review-entry.tsx"),
        "bank-review": path.resolve(__dirname, "src/bankReview/bank-review-entry.tsx"),
        "companion-overview": path.resolve(__dirname, "src/companion/companion-overview-entry.tsx"),
        "companion-issues": path.resolve(__dirname, "src/companion/companion-issues-entry.tsx"),
      },
      output: {
        assetFileNames: "assets/[name]-[hash][extname]",
        entryFileNames: "assets/[name]-[hash].js",
      },
    },
  },
  server: {
    port: 5173,
    strictPort: true,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setupTests.ts",
  },
});
