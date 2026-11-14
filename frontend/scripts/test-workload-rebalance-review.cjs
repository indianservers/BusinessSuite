const fs = require('node:fs');
const assert = require('node:assert/strict');
const ts = require('typescript');
const React = require('react');
const {renderToStaticMarkup} = require('react-dom/server');
const source = fs.readFileSync('src/components/ai-agents/WorkloadRebalanceReview.tsx','utf8');
const compiled = ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX}}).outputText;
const loaded = {exports:{}};
new Function('require','module','exports',compiled)(require,loaded,loaded.exports);
const Review = loaded.exports.default;
const review = {project_id:1,source_sha256:'abc',limitations:['Estimates are not reservations.'],changes:[{
 task_id:7,before_assignee_user_ids:[2],after_assignee_user_ids:[3],weeks:[{week_start:'2026-11-16',moved_hours:10,
 source_before_hours:30,source_after_hours:20,target_before_hours:5,target_after_hours:15,target_snapshot_capacity_hours:40}]}]};
const step = {tool:'pms.task_plan',record_id:1,payload:{workload_guard:{source_sha256:'abc',scope:'project',start:'2026-11-16',weeks:1},
 plan:{steps:[{tool:'update_task',task_id:7,changes:{assignee_user_ids:[3]}}]}}};
const render = (value,steps)=>renderToStaticMarkup(React.createElement(Review,{review:value,steps}));
const html = render(review,[step]);
assert.match(html,/Workload rebalance review/);
assert.match(html,/Current assignees: #2/);
assert.match(html,/Proposed assignees: #3/);
assert.match(html,/30 → 20 hours/);
assert.match(html,/5 → 15 hours/);
assert.match(html,/Estimates are not reservations/);
assert.equal(render({...review,source_sha256:'stale'},[step]),'');
const changed = structuredClone(step);
changed.payload.plan.steps[0].changes.assignee_user_ids=[4];
assert.equal(render(review,[changed]),'');
const extra = structuredClone(step);
extra.payload.plan.steps[0].changes.estimated_hours=100;
assert.equal(render(review,[extra]),'');
assert.equal(render(review,[]),'');
console.log('Workload review: matching estimates render; stale source and changed assignment stay hidden.');
