const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
const React = require('react');
const icons = require('lucide-react');
const filename = path.resolve(__dirname, '../src/shared/data-grid/column-presentation.tsx');
const compiled = ts.transpileModule(fs.readFileSync(filename, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2020 } }).outputText;
const loaded = new Module(filename, module);
loaded.filename = filename;
loaded.paths = Module._nodeModulePaths(path.dirname(filename));
loaded.require = function(specifier) {
  if (specifier === '@/shared/priority/priority') {
    const helperFile = path.resolve(__dirname, '../src/shared/priority/priority.ts');
    const helper = new Module(helperFile, module);
    helper.filename = helperFile;
    helper.paths = Module._nodeModulePaths(path.dirname(helperFile));
    helper._compile(ts.transpileModule(fs.readFileSync(helperFile, 'utf8'), {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText, helperFile);
    return helper.exports;
  }
  return Module.prototype.require.call(this, specifier);
};
loaded._compile(compiled, filename);
const { columnIcon, columnValue } = loaded.exports;
assert.equal(columnIcon('Vendor'), icons.Users, 'Vendor must not match the end-date icon');
assert.equal(columnIcon('Candidate'), icons.Columns3, 'Candidate must not match the date icon');
assert.equal(columnIcon('Due date'), icons.CalendarDays);
assert.equal(columnIcon('Joined'), icons.CalendarDays);
assert.equal(columnIcon('Debit'), icons.Wallet);
assert.equal(columnIcon('Currency'), icons.Wallet);
for (const value of ['0%', '42.5%', '100%']) {
  const result = columnValue('Completion', value);
  const meter = React.Children.toArray(result.props.children)[0];
  assert.equal(meter.props.role, 'progressbar');
  assert.equal(meter.props['aria-valuenow'], Number(value.slice(0,-1)));
}
for (const value of ['Unknown', '101%', '-1%', '50', null]) assert.equal(columnValue('Progress', value), value);
assert.equal(columnValue('Tax', '18%'), '18%', 'Unrelated percentages retain their domain meaning');
const editor = React.createElement('input', {value:'40%',readOnly:true});
assert.equal(columnValue('Progress', editor), editor, 'Custom cells must be preserved');
console.log('Column presentation checks passed');
