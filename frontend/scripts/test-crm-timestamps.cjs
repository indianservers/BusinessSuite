const fs = require('node:fs');
const assert = require('node:assert/strict');
const ts = require('typescript');
const source = fs.readFileSync('src/apps/crm/dateTime.ts', 'utf8');
const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
const mod = { exports: {} };
new Function('exports', 'module', output)(mod.exports, mod);
const { crmTimestamp } = mod.exports;
const instant = '2026-11-12T06:15:00.000Z';
for (const value of ['2026-11-12T06:15:00', '2026-11-12 06:15:00', '2026-11-12T06:15:00Z', '2026-11-12T11:45:00+05:30', new Date(instant)]) {
  assert.equal(crmTimestamp(value).toISOString(), instant);
}
assert.equal(crmTimestamp('2026-11-12T06:15:00.123456').toISOString(), '2026-11-12T06:15:00.123Z');
assert.equal(crmTimestamp('2026-11-12T06:15:00').toLocaleString('en-GB', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit' }), '11:45');
assert.equal(Number.isNaN(crmTimestamp('invalid').getTime()), true);
const { crmLocalDateTime } = mod.exports;
const originalZone = process.env.TZ;
process.env.TZ = 'Asia/Kolkata';
assert.equal(crmLocalDateTime('2026-11-12T06:15:00'), '2026-11-12T11:45');
assert.equal(crmLocalDateTime('2026-11-12T11:45:00+05:30'), '2026-11-12T11:45');
assert.equal(crmLocalDateTime(''), '');
assert.equal(crmLocalDateTime('invalid'), '');
if (originalZone === undefined) delete process.env.TZ; else process.env.TZ = originalZone;
console.log('12 CRM timestamp regression scenarios passed');
