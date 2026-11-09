import applicationConfig from "../vite.config.ts";

export default async environment => {
  const config=await (typeof applicationConfig === "function" ? applicationConfig(environment) : applicationConfig);
  return {
    ...config,
    cacheDir: "node_modules/.vite-module-regression",
    // QA pages should not reload when another workspace task edits a source file.
    server: { ...config.server, hmr: false },
    optimizeDeps: {
      ...config.optimizeDeps,
      // Exercise real application code without eagerly compiling unused ML models.
      include: ["react", "react-dom/client", "react/jsx-runtime", "react-router-dom", "@tanstack/react-query", "lucide-react"],
      entries: ["index.html", "launcher-enhancements-qa.html", "scripts/fixtures/priority-colors-qa.tsx"],
    },
  };
};
