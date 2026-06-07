import path from "path";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

type DevProxyResponse = {
  headersSent?: boolean;
  writeHead?: (statusCode: number, headers?: Record<string, string>) => void;
  end?: (body?: string) => void;
};

type DevProxy = {
  on: (event: "error", handler: (error: unknown, request: unknown, response?: DevProxyResponse) => void) => void;
};

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiProxyTarget = env.VITE_DEV_API_PROXY_TARGET || env.VITE_BACKEND_URL || "http://localhost:8001";
  const suppressProxyErrors = env.VITE_SUPPRESS_PROXY_ERRORS === "true";
  const configureProxy = suppressProxyErrors
    ? (proxy: DevProxy) => {
        proxy.on("error", (_error, _request, response) => {
          if (!response?.headersSent && response?.writeHead && response?.end) {
            response.writeHead(502, { "Content-Type": "application/json" });
            response.end(JSON.stringify({ detail: "Dev API proxy unavailable" }));
          }
        });
      }
    : undefined;

  return {
    plugins: [react()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: apiProxyTarget,
          changeOrigin: true,
          configure: configureProxy,
        },
        "/uploads": {
          target: apiProxyTarget,
          changeOrigin: true,
          configure: configureProxy,
        },
      },
    },
    build: {
      sourcemap: false,
      chunkSizeWarningLimit: 800,
      rollupOptions: {
        output: {
          manualChunks: {
            vendor: ["react", "react-dom", "react-router-dom"],
            ui: [
              "@radix-ui/react-dialog",
              "@radix-ui/react-dropdown-menu",
              "@radix-ui/react-select",
              "@radix-ui/react-tabs",
            ],
            charts: ["recharts"],
            query: ["@tanstack/react-query"],
            form: ["react-hook-form", "zod"],
          },
        },
      },
    },
  };
});
