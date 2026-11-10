import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("/node_modules/victory-vendor/")) return "vendor-victory";
          if (id.includes("/node_modules/recharts/")) return "vendor-charts";
          if (id.includes("/node_modules/lucide-react/")) return "vendor-icons";
        },
      },
    },
  },
});
