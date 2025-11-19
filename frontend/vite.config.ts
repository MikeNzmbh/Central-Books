import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  root: path.resolve(__dirname, "src"),
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
        "chart-of-accounts": path.resolve(__dirname, "src/chart-of-accounts.tsx"),
        "coa-account-detail": path.resolve(__dirname, "src/coa-account-detail.tsx"),
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
});
