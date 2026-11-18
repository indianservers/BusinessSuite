/* Idempotent migration: preserve every React cell and handler; replace only table shells. */
const fs = require("node:fs");
const path = require("node:path");
const ts = require("typescript");
const root = path.resolve(__dirname, "../src");
const changed = [];
function walk(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) { if (entry.name !== "data-grid") walk(file); continue; }
    if (!file.endsWith(".tsx")) continue;
    const original = fs.readFileSync(file, "utf8");
    const source = ts.createSourceFile(file, original, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
    const edits = [];
    let count = 0;
    function visit(node) {
      if (ts.isJsxElement(node) && node.openingElement.tagName.getText(source) === "table") {
        const name = path.relative(root, file).replaceAll(path.sep, "/").replace(/\.tsx$/, "");
        const id = `${name}:table-${++count}`;
        edits.push({ start: node.openingElement.tagName.getStart(source), end: node.openingElement.tagName.end, text: `GridTable gridId="${id}"` });
        edits.push({ start: node.closingElement.tagName.getStart(source), end: node.closingElement.tagName.end, text: "GridTable" });
      }
      ts.forEachChild(node, visit);
    }
    visit(source);
    if (!edits.length) continue;
    let output = original;
    for (const edit of edits.sort((a, b) => b.start - a.start)) output = output.slice(0, edit.start) + edit.text + output.slice(edit.end);
    output = 'import GridTable from "@/shared/data-grid/GridTable";\n' + output;
    fs.writeFileSync(file, output);
    changed.push({ file: path.relative(root, file).replaceAll(path.sep, "/"), tables: count });
  }
}
walk(root);
console.log(JSON.stringify({ files: changed.length, tables: changed.reduce((n, file) => n + file.tables, 0), changed }, null, 2));
