import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  resolve: { dedupe: ["react", "react-dom"] },
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
          vendor: ["react", "react-dom", "react-router-dom"],
        },
      },
    },
  },
});
