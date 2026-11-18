const ts = require("../node_modules/typescript"),
  fs = require("fs"),
  vm = require("vm"),
  path = require("path");
const root = path.resolve(__dirname, "../src");
function files(dir) {
  return fs
    .readdirSync(dir, { withFileTypes: true })
    .flatMap((e) =>
      e.isDirectory()
        ? files(path.join(dir, e.name))
        : [path.join(dir, e.name)],
    );
}
const output = [];
for (const file of files(root).filter((f) => f.endsWith("routes.tsx"))) {
  const source = fs.readFileSync(file, "utf8");
  const React = {
    createElement: (type, props) => ({
      component: type?.source || type?.name || String(type),
      props,
    }),
    lazy: (fn) => ({
      source:
        (fn.toString().match(/(?:import|require)\(["']([^"']+)/) || [])[1] ||
        "lazy",
    }),
    Fragment: "Fragment",
  };
  const stub = new Proxy(function () {}, {
    get: (_, key) =>
      key === "__esModule" ? true : key === "default" ? React : () => null,
  });
  const code = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      jsx: ts.JsxEmit.React,
      target: ts.ScriptTarget.ES2020,
    },
  }).outputText;
  const mod = { exports: {} };
  try {
    vm.runInNewContext(code, {
      exports: mod.exports,
      module: mod,
      require: (name) => {
        if (name === "react")
          return { __esModule: true, default: React, ...React };
        if (name.includes("sourceCatalog")) {
          const m = { exports: {} };
          vm.runInNewContext(
            ts.transpileModule(
              fs.readFileSync(
                path.join(root, "apps/inventory/sourceCatalog.ts"),
                "utf8",
              ),
              {
                compilerOptions: {
                  module: ts.ModuleKind.CommonJS,
                  target: ts.ScriptTarget.ES2020,
                },
              },
            ).outputText,
            { exports: m.exports, module: m, require: () => stub },
          );
          return m.exports;
        }
        return stub;
      },
      console,
    });
    for (const [name, routes] of Object.entries(mod.exports)) {
      if (!Array.isArray(routes) || !name.endsWith("Routes")) continue;
      for (const route of routes) {
        if (typeof route.path !== "string") continue;
        output.push({
          path: "/" + route.path.replace(/^\//, ""),
          source: path
            .relative(path.resolve(__dirname, "../.."), file)
            .replaceAll("\\", "/"),
          component: route.element?.component,
          variant: route.element?.props?.kind,
        });
      }
    }
  } catch (e) {
    throw Error(file + ": " + e.message);
  }
}
const previous = JSON.parse(
  fs.readFileSync(
    path.resolve(__dirname, "../../docs/ui-v2/route-coverage.json"),
    "utf8",
  ),
);
const byPath = new Map(
  previous.routes
    .filter((r) => r.source.endsWith("/App.tsx"))
    .map((r) => [r.path, r]),
);
for (const route of output) {
  const old = previous.routes.find((r) => r.path === route.path) || {};
  byPath.set(route.path, {
    ...old,
    ...route,
    module: route.path.startsWith("/hrms")
      ? "hrms"
      : route.source.includes("/hrms/")
        ? "hrms-legacy"
        : route.path.split("/")[1],
    dynamic: route.path.includes(":") || route.path.includes("*"),
    layout: ["/pms", "/pms/workspaces"].includes(route.path)
      ? "WorkspaceNavigation"
      : "AppLayout",
    implementation:
      "shared v2 tokens, components and shell applied; page-specific review pending",
    testing: "not yet verified",
    permissions: "Existing canAccessRoute and backend record authorization",
    dataDependencies: old.dataDependencies || [],
    actions: old.actions || [],
  });
}
const routes = [...byPath.values()];
const counts = {
  routes: routes.length,
  byModule: routes.reduce(
    (a, r) => ((a[r.module] = (a[r.module] || 0) + 1), a),
    {},
  ),
};
fs.writeFileSync(
  path.resolve(__dirname, "../../docs/ui-v2/route-coverage.json"),
  JSON.stringify(
    {
      generatedBy: "node frontend/scripts/audit-ui-routes.cjs",
      counts,
      routes,
    },
    null,
    2,
  ),
);
console.log(counts);
