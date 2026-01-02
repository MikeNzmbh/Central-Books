/// <reference types="vitest" />
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
      "@shared-ui": path.resolve(__dirname, "../shared-ui/src"),
    },
    // Ensure all shared-ui dependencies resolve from customer's node_modules
    dedupe: ["react", "react-dom", "framer-motion", "lucide-react"],
  },
  optimizeDeps: {
    include: ["framer-motion", "lucide-react"],
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    commonjsOptions: {
      include: [/node_modules/],
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
