// vite.config.mts
import { defineConfig } from "file:///C:/central_books/Central-Books-1/apps/customer/node_modules/vitest/dist/config.js";
import react from "file:///C:/central_books/Central-Books-1/apps/customer/node_modules/@vitejs/plugin-react/dist/index.js";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { visualizer } from "file:///C:/central_books/Central-Books-1/apps/customer/node_modules/rollup-plugin-visualizer/dist/plugin/index.js";
var __vite_injected_original_import_meta_url = "file:///C:/central_books/Central-Books-1/apps/customer/vite.config.mts";
var __dirname = path.dirname(fileURLToPath(__vite_injected_original_import_meta_url));
var vite_config_default = defineConfig(({ mode }) => {
  const reportPath = process.env.BUNDLE_REPORT;
  const shouldAnalyze = mode === "analyze" || Boolean(reportPath);
  return {
    plugins: [
      react(),
      ...shouldAnalyze ? [
        visualizer({
          filename: reportPath || path.resolve(__dirname, "../../docs/perf/bundle-report.html"),
          template: "treemap",
          gzipSize: true,
          brotliSize: true,
          open: false
        })
      ] : []
    ],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "src"),
        "@shared-ui": path.resolve(__dirname, "../shared-ui/src")
      },
      // Ensure all shared-ui dependencies resolve from customer's node_modules
      dedupe: ["react", "react-dom", "framer-motion", "lucide-react"]
    },
    optimizeDeps: {
      include: ["framer-motion", "lucide-react"]
    },
    build: {
      outDir: "dist",
      emptyOutDir: true,
      commonjsOptions: {
        include: [/node_modules/]
      }
    },
    server: {
      host: "0.0.0.0",
      port: 5173,
      strictPort: true,
      proxy: {
        // Forward API requests to Rust backend
        "/api": {
          target: "http://localhost:3001",
          changeOrigin: true,
          secure: false
        }
      }
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: "./src/test/setupTests.ts"
    }
  };
});
export {
  vite_config_default as default
};
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsidml0ZS5jb25maWcubXRzIl0sCiAgInNvdXJjZXNDb250ZW50IjogWyJjb25zdCBfX3ZpdGVfaW5qZWN0ZWRfb3JpZ2luYWxfZGlybmFtZSA9IFwiQzpcXFxcY2VudHJhbF9ib29rc1xcXFxDZW50cmFsLUJvb2tzLTFcXFxcYXBwc1xcXFxjdXN0b21lclwiO2NvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9maWxlbmFtZSA9IFwiQzpcXFxcY2VudHJhbF9ib29rc1xcXFxDZW50cmFsLUJvb2tzLTFcXFxcYXBwc1xcXFxjdXN0b21lclxcXFx2aXRlLmNvbmZpZy5tdHNcIjtjb25zdCBfX3ZpdGVfaW5qZWN0ZWRfb3JpZ2luYWxfaW1wb3J0X21ldGFfdXJsID0gXCJmaWxlOi8vL0M6L2NlbnRyYWxfYm9va3MvQ2VudHJhbC1Cb29rcy0xL2FwcHMvY3VzdG9tZXIvdml0ZS5jb25maWcubXRzXCI7Ly8vIDxyZWZlcmVuY2UgdHlwZXM9XCJ2aXRlc3RcIiAvPlxyXG5pbXBvcnQgeyBkZWZpbmVDb25maWcgfSBmcm9tIFwidml0ZXN0L2NvbmZpZ1wiO1xyXG5pbXBvcnQgcmVhY3QgZnJvbSBcIkB2aXRlanMvcGx1Z2luLXJlYWN0XCI7XHJcbmltcG9ydCBwYXRoIGZyb20gXCJub2RlOnBhdGhcIjtcclxuaW1wb3J0IHsgZmlsZVVSTFRvUGF0aCB9IGZyb20gXCJub2RlOnVybFwiO1xyXG5pbXBvcnQgeyB2aXN1YWxpemVyIH0gZnJvbSBcInJvbGx1cC1wbHVnaW4tdmlzdWFsaXplclwiO1xyXG5cclxuY29uc3QgX19kaXJuYW1lID0gcGF0aC5kaXJuYW1lKGZpbGVVUkxUb1BhdGgoaW1wb3J0Lm1ldGEudXJsKSk7XHJcblxyXG5leHBvcnQgZGVmYXVsdCBkZWZpbmVDb25maWcoKHsgbW9kZSB9KSA9PiB7XHJcbiAgY29uc3QgcmVwb3J0UGF0aCA9IHByb2Nlc3MuZW52LkJVTkRMRV9SRVBPUlQ7XHJcbiAgY29uc3Qgc2hvdWxkQW5hbHl6ZSA9IG1vZGUgPT09IFwiYW5hbHl6ZVwiIHx8IEJvb2xlYW4ocmVwb3J0UGF0aCk7XHJcblxyXG4gIHJldHVybiB7XHJcbiAgICBwbHVnaW5zOiBbXHJcbiAgICAgIHJlYWN0KCksXHJcbiAgICAgIC4uLihzaG91bGRBbmFseXplXHJcbiAgICAgICAgPyBbXHJcbiAgICAgICAgICAgIHZpc3VhbGl6ZXIoe1xyXG4gICAgICAgICAgICAgIGZpbGVuYW1lOlxyXG4gICAgICAgICAgICAgICAgcmVwb3J0UGF0aCB8fFxyXG4gICAgICAgICAgICAgICAgcGF0aC5yZXNvbHZlKF9fZGlybmFtZSwgXCIuLi8uLi9kb2NzL3BlcmYvYnVuZGxlLXJlcG9ydC5odG1sXCIpLFxyXG4gICAgICAgICAgICAgIHRlbXBsYXRlOiBcInRyZWVtYXBcIixcclxuICAgICAgICAgICAgICBnemlwU2l6ZTogdHJ1ZSxcclxuICAgICAgICAgICAgICBicm90bGlTaXplOiB0cnVlLFxyXG4gICAgICAgICAgICAgIG9wZW46IGZhbHNlLFxyXG4gICAgICAgICAgICB9KSxcclxuICAgICAgICAgIF1cclxuICAgICAgICA6IFtdKSxcclxuICAgIF0sXHJcbiAgICByZXNvbHZlOiB7XHJcbiAgICAgIGFsaWFzOiB7XHJcbiAgICAgICAgXCJAXCI6IHBhdGgucmVzb2x2ZShfX2Rpcm5hbWUsIFwic3JjXCIpLFxyXG4gICAgICAgIFwiQHNoYXJlZC11aVwiOiBwYXRoLnJlc29sdmUoX19kaXJuYW1lLCBcIi4uL3NoYXJlZC11aS9zcmNcIiksXHJcbiAgICAgIH0sXHJcbiAgICAgIC8vIEVuc3VyZSBhbGwgc2hhcmVkLXVpIGRlcGVuZGVuY2llcyByZXNvbHZlIGZyb20gY3VzdG9tZXIncyBub2RlX21vZHVsZXNcclxuICAgICAgZGVkdXBlOiBbXCJyZWFjdFwiLCBcInJlYWN0LWRvbVwiLCBcImZyYW1lci1tb3Rpb25cIiwgXCJsdWNpZGUtcmVhY3RcIl0sXHJcbiAgICB9LFxyXG4gICAgb3B0aW1pemVEZXBzOiB7XHJcbiAgICAgIGluY2x1ZGU6IFtcImZyYW1lci1tb3Rpb25cIiwgXCJsdWNpZGUtcmVhY3RcIl0sXHJcbiAgICB9LFxyXG4gICAgYnVpbGQ6IHtcclxuICAgICAgb3V0RGlyOiBcImRpc3RcIixcclxuICAgICAgZW1wdHlPdXREaXI6IHRydWUsXHJcbiAgICAgIGNvbW1vbmpzT3B0aW9uczoge1xyXG4gICAgICAgIGluY2x1ZGU6IFsvbm9kZV9tb2R1bGVzL10sXHJcbiAgICAgIH0sXHJcbiAgICB9LFxyXG4gICAgc2VydmVyOiB7XHJcbiAgICAgIGhvc3Q6IFwiMC4wLjAuMFwiLFxyXG4gICAgICBwb3J0OiA1MTczLFxyXG4gICAgICBzdHJpY3RQb3J0OiB0cnVlLFxyXG4gICAgICBwcm94eToge1xyXG4gICAgICAgIC8vIEZvcndhcmQgQVBJIHJlcXVlc3RzIHRvIFJ1c3QgYmFja2VuZFxyXG4gICAgICAgIFwiL2FwaVwiOiB7XHJcbiAgICAgICAgICB0YXJnZXQ6IFwiaHR0cDovL2xvY2FsaG9zdDozMDAxXCIsXHJcbiAgICAgICAgICBjaGFuZ2VPcmlnaW46IHRydWUsXHJcbiAgICAgICAgICBzZWN1cmU6IGZhbHNlLFxyXG4gICAgICAgIH0sXHJcbiAgICAgIH0sXHJcbiAgICB9LFxyXG4gICAgdGVzdDoge1xyXG4gICAgICBlbnZpcm9ubWVudDogXCJqc2RvbVwiLFxyXG4gICAgICBnbG9iYWxzOiB0cnVlLFxyXG4gICAgICBzZXR1cEZpbGVzOiBcIi4vc3JjL3Rlc3Qvc2V0dXBUZXN0cy50c1wiLFxyXG4gICAgfSxcclxuICB9O1xyXG59KTtcclxuIl0sCiAgIm1hcHBpbmdzIjogIjtBQUNBLFNBQVMsb0JBQW9CO0FBQzdCLE9BQU8sV0FBVztBQUNsQixPQUFPLFVBQVU7QUFDakIsU0FBUyxxQkFBcUI7QUFDOUIsU0FBUyxrQkFBa0I7QUFMbUwsSUFBTSwyQ0FBMkM7QUFPL1AsSUFBTSxZQUFZLEtBQUssUUFBUSxjQUFjLHdDQUFlLENBQUM7QUFFN0QsSUFBTyxzQkFBUSxhQUFhLENBQUMsRUFBRSxLQUFLLE1BQU07QUFDeEMsUUFBTSxhQUFhLFFBQVEsSUFBSTtBQUMvQixRQUFNLGdCQUFnQixTQUFTLGFBQWEsUUFBUSxVQUFVO0FBRTlELFNBQU87QUFBQSxJQUNMLFNBQVM7QUFBQSxNQUNQLE1BQU07QUFBQSxNQUNOLEdBQUksZ0JBQ0E7QUFBQSxRQUNFLFdBQVc7QUFBQSxVQUNULFVBQ0UsY0FDQSxLQUFLLFFBQVEsV0FBVyxvQ0FBb0M7QUFBQSxVQUM5RCxVQUFVO0FBQUEsVUFDVixVQUFVO0FBQUEsVUFDVixZQUFZO0FBQUEsVUFDWixNQUFNO0FBQUEsUUFDUixDQUFDO0FBQUEsTUFDSCxJQUNBLENBQUM7QUFBQSxJQUNQO0FBQUEsSUFDQSxTQUFTO0FBQUEsTUFDUCxPQUFPO0FBQUEsUUFDTCxLQUFLLEtBQUssUUFBUSxXQUFXLEtBQUs7QUFBQSxRQUNsQyxjQUFjLEtBQUssUUFBUSxXQUFXLGtCQUFrQjtBQUFBLE1BQzFEO0FBQUE7QUFBQSxNQUVBLFFBQVEsQ0FBQyxTQUFTLGFBQWEsaUJBQWlCLGNBQWM7QUFBQSxJQUNoRTtBQUFBLElBQ0EsY0FBYztBQUFBLE1BQ1osU0FBUyxDQUFDLGlCQUFpQixjQUFjO0FBQUEsSUFDM0M7QUFBQSxJQUNBLE9BQU87QUFBQSxNQUNMLFFBQVE7QUFBQSxNQUNSLGFBQWE7QUFBQSxNQUNiLGlCQUFpQjtBQUFBLFFBQ2YsU0FBUyxDQUFDLGNBQWM7QUFBQSxNQUMxQjtBQUFBLElBQ0Y7QUFBQSxJQUNBLFFBQVE7QUFBQSxNQUNOLE1BQU07QUFBQSxNQUNOLE1BQU07QUFBQSxNQUNOLFlBQVk7QUFBQSxNQUNaLE9BQU87QUFBQTtBQUFBLFFBRUwsUUFBUTtBQUFBLFVBQ04sUUFBUTtBQUFBLFVBQ1IsY0FBYztBQUFBLFVBQ2QsUUFBUTtBQUFBLFFBQ1Y7QUFBQSxNQUNGO0FBQUEsSUFDRjtBQUFBLElBQ0EsTUFBTTtBQUFBLE1BQ0osYUFBYTtBQUFBLE1BQ2IsU0FBUztBQUFBLE1BQ1QsWUFBWTtBQUFBLElBQ2Q7QUFBQSxFQUNGO0FBQ0YsQ0FBQzsiLAogICJuYW1lcyI6IFtdCn0K
