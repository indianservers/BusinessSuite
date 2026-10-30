const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const ts = require("typescript");
const memory = new Map();
global.localStorage = { getItem: key => memory.get(key) || null, setItem: (key, value) => memory.set(key, value), removeItem: key => memory.delete(key) };
function loadStore() {
  const source = fs.readFileSync(path.resolve(__dirname, "../src/store/pmsNavigation.ts"), "utf8");
  const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
  const compiled = { exports: {} };
  new Function("module", "exports", "require", output)(compiled, compiled.exports, require);
  return compiled.exports.usePmsNavigation;
}
localStorage.setItem("kf-navigation-7", JSON.stringify({ recent: [{ path:"/pms/projects", label:"Projects" }], visits: { "/pms/projects": 9, "/hrms": 20 } }));
const useStore = loadStore();
const scope = "7:1";
useStore.getState().visit(scope, { path:"/pms/notes", label:"Notes" }, 7);
assert.equal(useStore.getState().contexts[scope].visits["/pms/projects"], 9, "Existing Top 5 history was not migrated");
assert.equal(useStore.getState().contexts[scope].visits["/hrms"], undefined);
useStore.getState().pin(scope, { path:"/pms/notes", label:"Notes" });
useStore.getState().pin(scope, { path:"/pms/projects", label:"Projects" });
useStore.getState().move(scope, "/pms/projects", -1);
for (let i=0;i<8;i++) {
  useStore.getState().visit(scope, { path:`/pms/projects/${i}`, label:`Project ${i}` }, 7);
  useStore.getState().visit(scope, { path:"/pms/notes", label:"Notes" }, 7);
}
const pinned = useStore.getState().contexts[scope].favorites.map(p => p.path);
assert.deepEqual(pinned, ["/pms/projects", "/pms/notes"], "Visits changed the explicit favorite order");
const reloaded = loadStore();
assert.deepEqual(reloaded.getState().contexts[scope].favorites.map(p => p.path), pinned, "Favorite order changed after reload");
reloaded.getState().visit("7:2", { path:"/pms/members", label:"People" }, 7);
assert.deepEqual(reloaded.getState().contexts["7:2"].favorites, [], "Favorites leaked into another organization");
assert.equal(reloaded.getState().contexts["7:2"].visits["/pms/projects"], undefined, "Visit history leaked into another organization");
reloaded.getState().visit("8:1", { path:"/pms/members", label:"People" }, 8);
assert.deepEqual(reloaded.getState().contexts["8:1"].favorites, [], "Preferences leaked into another account");
const before = reloaded.getState().contexts["8:1"].visits["/pms/members"];
reloaded.getState().visit("8:1", { path:"/pms/members", label:"People" }, 8);
assert.equal(reloaded.getState().contexts["8:1"].visits["/pms/members"], before, "Render/reload double-counted the same page");
assert.equal(new Set(reloaded.getState().contexts[scope].recent.map(p => p.path)).size, reloaded.getState().contexts[scope].recent.length, "Recent pages contain duplicates");
console.log("PMS personal navigation passed: legacy Top 5, stable pin order, reload persistence, distinct recents, account and organization isolation.");
