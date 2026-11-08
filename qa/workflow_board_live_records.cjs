// Creates clearly tagged, reversible records through the running application's APIs.
const { auth } = require('./custom_fields_live.cjs');
const fs = require('node:fs'), path = require('node:path');
const file = path.resolve('.tmp/workflow-board-live-records.json');
const state = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')) : { run: 'WFV' + Date.now(), records: {} };
const save = () => { fs.mkdirSync(path.dirname(file), { recursive: true }); fs.writeFileSync(file, JSON.stringify(state, null, 2)); };
const list = data => Array.isArray(data) ? data : data.items || [];
const day = offset => { const d = new Date(); d.setDate(d.getDate() + offset); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
(async () => {
  const { api, actor } = await auth();
  if (!state.records.deal) {
    const stages = list(await api('/crm/deal-workspace/pipeline-stages')).filter(s => !s.is_won && !s.is_lost);
    const first = stages[0], second = stages.find(s => s.pipeline_id === first.pipeline_id && s.id !== first.id);
    const source = list(await api('/crm/deal-workspace/query?per_page=1'))[0];
    const deal = await api('/crm/deals', 'POST', { name: state.run + ' dashboard deal', pipeline_id: first.pipeline_id, stage_id: first.id, company_id: source.company_id, contact_id: source.contact_id, amount: 1, currency: 'INR', expected_close_date: day(-1), owner_user_id: actor.id });
    state.records.deal = { id: deal.id, title: deal.name, originalStage: first.id, targetStage: second.id }; save();
  }
  if (!state.records.candidate) {
    const jobs = list(await api('/recruitment/jobs'));
    const job = jobs.find(j => /QA|test/i.test(j.title)) || jobs[0];
    const candidate = await api('/recruitment/candidates', 'POST', { job_id: job.id, first_name: state.run, last_name: 'dashboard candidate', email: state.run.toLowerCase() + '@example.com', source: 'Dashboard live verification' });
    state.records.candidate = { id: candidate.id, title: candidate.first_name + ' ' + candidate.last_name, jobId: job.id }; save();
  }
  if (!state.records.task) {
    const projects = list(await api('/project-management/projects?limit=100'));
    const project = projects.find(p => /Suite QA/.test(p.name)) || projects.find(p => /QA/.test(p.name));
    const task = await api(`/project-management/projects/${project.id}/tasks`, 'POST', { title: state.run + ' dashboard task', task_key: state.run, status: 'To Do', priority: 'High', due_date: '2026-01-01', estimated_hours: 1, assignee_user_id: actor.id });
    state.records.task = { id: task.id, title: task.title, projectId: project.id, workspaceId: project.workspace_id }; save();
  }
  if (!state.records.order) {
    const order = await api('/srm/sales-orders', 'POST', { order_number: state.run, title: state.run + ' dashboard order', currency: 'INR', expected_end_date: day(-1), subtotal: 1, total_amount: 1, lines: [{ service_type: 'service', description: 'Dashboard live verification only', quantity: 1, unit_price: 1, line_total: 1 }] });
    state.records.order = { id: order.id, title: order.order_number }; save();
  }
  if (!state.records.bills) {
    const party = list(await api('/fam/parties')).find(p => ['customer', 'both'].includes(p.party_type));
    const ledger = list(await api('/fam/ledgers'))[0];
    state.records.bills = []; save();
    for (const offset of [3, 0, -7, -35, -70]) {
      const bill = await api('/fam/bill-references', 'POST', { party_id: party.id, ledger_id: ledger.id, bill_number: state.run + '-' + Math.abs(offset), bill_date: day(-80), due_date: day(offset), bill_type: 'invoice', original_amount: '0.01', source_record_type: 'workflow_board_live_verification', source_record_id: state.run });
      state.records.bills.push({ id: bill.id, title: bill.bill_number, due: bill.due_date, partyId: party.id, companyId: bill.company_id }); save();
    }
  }
  if (!state.records.policy) {
    const policy = await api('/power-apps/approvals/policies?environment=development', 'POST', { name: state.run + ' dashboard approval', definition: { stages: [{ id: 'review', name: 'Verification review', selectors: [{ kind: 'organization_owner' }] }], fields: [], prohibit_self_approval: true, documents_required: false } });
    state.records.policy = { id: policy.id, name: policy.name, version: policy.version }; save();
    await api(`/power-apps/approvals/policies/${policy.id}/activate?environment=development&expected_version=${policy.version}`, 'POST');
  }
  if (!state.records.approval) {
    const request = await api('/power-apps/approvals/requests?environment=development', 'POST', { policy_id: state.records.policy.id, title: state.run + ' dashboard approval', description: 'Live dashboard verification; no purchase, payment, or message dispatch.', request_key: state.run, fields: {} });
    state.records.approval = { id: request.id, title: request.title, status: request.status }; save();
  }
  console.log(JSON.stringify({ run: state.run, created: state.records }));
})().catch(error => { console.error(error.message); save(); process.exitCode = 1; });
