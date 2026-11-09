import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  // Shared suite components must use the portal's router context too.
  resolve: { alias: { "@": fileURLToPath(new URL("../src", import.meta.url)) }, dedupe: ["react", "react-dom", "react-router", "react-router-dom", "@tanstack/react-query"] },
  plugins: [react()],
  server: {
    fs: { allow: [".."] },
    port: 5178,
    proxy: {
      "/uploads": {
        target: process.env.HRMS_API_PROXY || "http://127.0.0.1:1534",
        changeOrigin: true,
      },
      "/api": {
        target: process.env.HRMS_API_PROXY || "http://127.0.0.1:1534",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          charts: ["recharts"],
          vendor: ["react", "react-dom", "react-router-dom", "@tanstack/react-query"],
        },
      },
    },
  },
});
