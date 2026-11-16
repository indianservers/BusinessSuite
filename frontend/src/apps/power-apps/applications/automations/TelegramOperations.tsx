import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '@/services/api';
import { errorMessage } from '../../api';
import type { Environment } from '../../registry';
import type { TelegramAudience } from './TelegramInterfaceSettings';

type Identity = { id: number; interface: string; telegram_user_id: string; name: string; verified: boolean; employee_id?: number; user_id?: number; contact_id?: number; lead_id?: number };
type ThreadContext = { language?: string; qualification?: { qualified: boolean; priority: string; reasons: string[] }; routing?: { reason: string }; sla_due_at?: string; sla_waiting?: boolean; sla_breached?: boolean; service_stage?: string; stage_revision?: number; stage_approved?: boolean; workflow_id?: string };
type ReplyDraft = { id: number; text: string; expires_at: string; sources: { id: string; reference: string; url: string }[] };
type Thread = { context?: ThreadContext; service_stages?: { key: string; label: string; requires_approval: boolean; next_stages: string[] }[]; id: number; interface: string; chat_id: string; status: string; assignee_user_id?: number; lead_id?: number; task_id?: number; messages: { id: number; direction: string; text: string; delivery_status?: string; run_id?: number }[] };
type Operations = { stage_reviews?: { id: number; can_review: boolean; expires_at: string; operation: { conversation_id: number; from_stage: string; target: string } }[]; identities: Identity[]; conversations: Thread[]; current_user_id: number; can_manage: boolean };
type Employee = { id: number; employee_code: string; name: string; user_id: number };

export function TelegramOperations({ resourceId, environment, canManage, canExecute, audience = 'shared' }: { resourceId: number; environment: Environment; canManage: boolean; canExecute: boolean; audience?: TelegramAudience }) {
  const base = `/power-apps/automations/telegram/${resourceId}`;
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<Operations>();
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [employeeId, setEmployeeId] = useState('');
  const [telegramId, setTelegramId] = useState('');
  const [publicType, setPublicType] = useState('contact');
  const [publicId, setPublicId] = useState('');
  const [command, setCommand] = useState('');
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [selectedId, setSelectedId] = useState<number>();
  const [filter, setFilter] = useState('all');
  const [assignee, setAssignee] = useState('');
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [suggestions, setSuggestions] = useState<Record<number, ReplyDraft>>({});
  const [stageTarget, setStageTarget] = useState('');
  const [replyKeys, setReplyKeys] = useState<Record<number, string>>({});
  useEffect(() => {
    setCommand(''); setData(undefined); setSelectedId(undefined); setSuggestions({}); setDrafts({}); setReplyKeys({});
    setEmployees([]); setEmployeeId(''); setTelegramId(''); setPublicId(''); setAssignee(''); setStageTarget(''); setStatus(''); setError('');
  }, [audience]);
  useEffect(() => {
    if (!open) return;
    let active = true;
    const load = async () => {
      try { const result = await api.get<Operations>(`${base}/operations`, { params: { environment } }); if (active) setData(result.data); }
      catch (err) { if (active) setError(errorMessage(err)); }
    };
    void load(); const timer = window.setInterval(() => void load(), 8000);
    return () => { active = false; window.clearInterval(timer); };
  }, [base, environment, open, refresh, audience]);
  useEffect(() => {
    if (!open || !canManage || audience === 'public') return;
    let active = true;
    void api.get<{ items: Employee[] }>(`${base}/employee-options`, { params: { environment } }).then(result => { if (active) setEmployees(result.data.items || []); }).catch(() => { if (active) setEmployees([]); });
    return () => { active = false; };
  }, [base, environment, open, canManage, audience]);
  async function action(work: () => Promise<unknown>, success: string) {
    setBusy(true); setError(''); setStatus('');
    try { await work(); setStatus(success); setRefresh(value => value + 1); }
    catch (err) { setError(errorMessage(err)); }
    finally { setBusy(false); }
  }
  const visibleThreads = (data?.conversations || []).filter(thread => audience === 'shared' || thread.interface === audience);
  const identities = (data?.identities || []).filter(link => audience === 'shared' || link.interface === audience);
  const threads = visibleThreads.filter(thread => filter === 'all' || thread.status === filter);
  const selected = visibleThreads.find(thread => thread.id === selectedId);
  return <details className="telegram-operations" onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>Identity linking & human handoff</summary>
    {open && <>
      <p>{audience === 'public' ? 'Public visitors can enquire without a customer account. Verify their account link before sharing private information.' : audience === 'company' ? 'Company access follows the linked employee and their current BusinessSuite permissions.' : 'This legacy bot still serves employees and public customers until its purpose is saved.'} Send /human to request a person. Staff can manage the handoff inbox below.</p>
      {error && <p role="alert">{error}</p>}{status && <p role="status">{status}</p>}
      {canManage && <div className="telegram-interfaces">
        {audience !== 'public' && <form className="telegram-setup" onSubmit={event => { event.preventDefault(); void action(async () => {
          await api.post(`${base}/employee-links`, { employee_id: Number(employeeId), telegram_user_id: telegramId.trim() }, { params: { environment } });
          setTelegramId('');
        }, 'Employee linked. Company authorization is automatic on their next message.'); }}>
          <h5>Link an employee</h5>
          <label>Employee<select required value={employeeId} onChange={event => setEmployeeId(event.target.value)} disabled={busy}><option value="">Choose an employee</option>{employees.map(employee => <option key={employee.id} value={employee.id}>{employee.name} · {employee.employee_code}</option>)}</select></label>
          <p>Lists up to 200 active employees with a BusinessSuite user account. Employee update permission is required. Employees can send /id to this bot, then /start after linking.</p>
          <label>Employee Telegram user ID<input required inputMode="numeric" pattern="[1-9][0-9]{0,19}" value={telegramId} onChange={event => setTelegramId(event.target.value)} disabled={busy} /></label>
          <button disabled={busy || !employeeId} type="submit">Link employee Telegram ID</button>
        </form>}
        {audience !== 'company' && <form className="telegram-setup" onSubmit={event => { event.preventDefault(); setCommand(''); void action(async () => {
          const result = await api.post<{ command: string }>(`${base}/link-code`, { interface: 'public', [publicType === 'contact' ? 'contact_id' : publicType === 'lead' ? 'lead_id' : 'customer_id']: Number(publicId) }, { params: { environment } });
          setCommand(result.data.command);
        }, 'Customer link code generated. It expires in 10 minutes and works once.'); }}>
          <h5>Link an existing public customer</h5>
          <label>CRM record type<select value={publicType} onChange={event => setPublicType(event.target.value)}><option value="contact">Contact</option><option value="lead">Lead</option><option value="customer">Customer account</option></select></label>
          <label>CRM record ID<input required type="number" min={1} step={1} value={publicId} onChange={event => setPublicId(event.target.value)} /></label>
          <p>Share the one-time command privately with the verified customer. They send it to this bot. Names and usernames never auto-link a customer.</p>
          <button type="submit" disabled={busy}>Generate customer linking code</button>
        </form>}
      </div>}
      {audience !== 'public' && <button type="button" disabled={busy} onClick={() => { setCommand(''); void action(async () => {
        const result = await api.post<{ command: string }>(`${base}/link-code`, { interface: 'company' }, { params: { environment } }); setCommand(result.data.command);
      }, 'Your account link code expires in 10 minutes. Send it privately to this bot.'); }}>Generate my company link code</button>}
      {command && <label>One-time Telegram command<input readOnly value={command} onFocus={event => event.target.select()} /></label>}
      {canManage && identities.length > 0 && <section aria-label="Linked Telegram identities"><h5>Linked identities</h5>{identities.map(link => <div key={link.id} className="telegram-identity"><span>{link.name || link.telegram_user_id} · {link.interface} · {link.verified ? 'Linked' : 'Telegram visitor'} · ID {link.telegram_user_id}{link.employee_id && <> · <Link to={`/hrms/employees/${link.employee_id}`}>Employee #{link.employee_id}</Link></>}</span>{link.verified && <button type="button" disabled={busy} onClick={() => void action(() => api.delete(`${base}/identities/${link.id}`, { params: { environment } }), 'Identity revoked. Verified access ends immediately.')}>Revoke link</button>}</div>)}</section>}
      <header><h5>Conversation inbox</h5><label>Conversation status<select value={filter} onChange={event => setFilter(event.target.value)}><option value="all">All conversations</option><option value="waiting">Waiting for a person</option><option value="assigned">Assigned</option><option value="bot">Bot active</option><option value="resolved">Resolved</option></select></label><button type="button" onClick={() => setRefresh(value => value + 1)}>Refresh inbox</button></header>
      <p>The inbox shows the 50 most recent conversations and up to 50 recent messages per conversation. Outgoing messages show execution status; queued does not mean delivered.</p>
      <div className="telegram-inbox"><nav aria-label="Telegram conversations">{threads.map(thread => <button type="button" aria-pressed={selectedId === thread.id} key={thread.id} onClick={() => { setSelectedId(thread.id); setAssignee(''); setStageTarget(''); }}>{thread.interface} · Chat {thread.chat_id}<br />{thread.status}{thread.assignee_user_id ? ` · User #${thread.assignee_user_id}` : ''}</button>)}{!threads.length && <p>No conversations match this filter.</p>}</nav>
        {selected ? <section aria-label={`Conversation ${selected.id}`}>
          <h5>{selected.interface === 'company' ? 'Company' : 'Public'} conversation #{selected.id} · {selected.status}</h5>
          <p>{selected.lead_id && <Link to={`/crm/leads/${selected.lead_id}`}>CRM lead #{selected.lead_id}</Link>}{selected.task_id && <> · <Link to="/crm/tasks">CRM task #{selected.task_id}</Link></>}</p>
          {selected.context?.qualification && <div className="telegram-enquiry"><strong>Qualification: {selected.context.qualification.qualified ? 'Complete' : 'Needs information'} · {selected.context.qualification.priority}</strong>{selected.context.qualification.reasons.map((reason, index) => <p key={index}>{reason}</p>)}</div>}
          {selected.context?.routing && <p>Routing: {selected.context.routing.reason}</p>}
          {selected.context?.sla_waiting && <p className={selected.context.sla_breached ? 'pa-error' : undefined}>{selected.context.sla_breached ? 'Response deadline breached' : 'Staff response due'} · {selected.context.sla_due_at && new Date(selected.context.sla_due_at).toLocaleString()}</p>}
          {selected.context?.service_stage && <section aria-label="Service stage"><p>Service stage: {selected.service_stages?.find(stage => stage.key === selected.context?.service_stage)?.label || selected.context.service_stage}{selected.context.stage_approved === false ? ' · Awaiting approval' : ''}</p>
            {canExecute && <form className="telegram-controls" onSubmit={event => { event.preventDefault(); void action(() => api.post(`${base}/conversations/${selected.id}/stage`, { target: stageTarget, expected_revision: selected.context?.stage_revision || 0 }, { params: { environment } }), 'Service stage request recorded. Required approvals remain pending.'); }}><label>Next service stage<select required value={stageTarget} onChange={event => setStageTarget(event.target.value)}><option value="">Choose next stage</option>{selected.service_stages?.filter(stage => selected.service_stages?.find(current => current.key === selected.context?.service_stage)?.next_stages.includes(stage.key)).map(stage => <option key={stage.key} value={stage.key}>{stage.label}{stage.requires_approval ? ' · approval required' : ''}</option>)}</select></label><button type="submit" disabled={busy || !stageTarget}>Move service stage</button></form>}
            {data?.stage_reviews?.filter(review => review.operation.conversation_id === selected.id).map(review => <div className="telegram-question" key={review.id}><p>Review entry into {selected.service_stages?.find(stage => stage.key === review.operation.target)?.label || review.operation.target}. Expires {new Date(review.expires_at).toLocaleString()}.</p>{review.can_review && canExecute ? <div className="telegram-controls"><button type="button" disabled={busy} onClick={() => void action(() => api.post(`${base}/stage-reviews/${review.id}`, { approved: true }, { params: { environment } }), 'Service stage approved.')}>Approve service stage</button><button type="button" disabled={busy} onClick={() => void action(() => api.post(`${base}/stage-reviews/${review.id}`, { approved: false }, { params: { environment } }), 'Service stage rejected.')}>Reject service stage</button></div> : <p>Waiting for an authorized workflow reviewer.</p>}</div>)}
          </section>}
          <div className="telegram-transcript">{selected.messages.map(message => <div key={message.id} className="telegram-message"><strong>{message.direction === 'incoming' ? 'Telegram user' : message.direction === 'system' ? 'Activity' : 'BusinessSuite'}{message.delivery_status ? ` · ${message.delivery_status}` : ''}</strong><p>{message.text}</p></div>)}</div>
          {canExecute && <>
            <div className="telegram-controls">{selected.assignee_user_id !== data?.current_user_id && <button type="button" disabled={busy} onClick={() => void action(() => api.put(`${base}/conversations/${selected.id}`, { action: 'claim' }, { params: { environment } }), 'Conversation claimed. Automatic replies are paused.')}>Claim conversation</button>}<button type="button" disabled={busy} onClick={() => void action(() => api.put(`${base}/conversations/${selected.id}`, { action: 'resolve' }, { params: { environment } }), 'Conversation resolved.')}>Resolve</button><button type="button" disabled={busy} onClick={() => void action(() => api.put(`${base}/conversations/${selected.id}`, { action: 'resume' }, { params: { environment } }), 'Conversation returned to the bot.')}>Return to bot</button></div>
            {canManage && <form className="telegram-controls" onSubmit={event => { event.preventDefault(); void action(() => api.put(`${base}/conversations/${selected.id}`, { action: 'assign', assignee_user_id: Number(assignee) }, { params: { environment } }), 'Conversation assigned.'); }}><label>Assign to BusinessSuite user ID<input required type="number" min={1} step={1} value={assignee} onChange={event => setAssignee(event.target.value)} /></label><button type="submit" disabled={busy}>Assign</button></form>}
            <button type="button" disabled={busy || selected.status !== 'assigned' || selected.assignee_user_id !== data?.current_user_id} onClick={() => { const id = selected.id; void action(async () => { const response = await api.post<ReplyDraft>(`${base}/conversations/${id}/draft`, {}, { params: { environment } }); setSuggestions(value => ({ ...value, [id]: response.data })); setDrafts(value => ({ ...value, [id]: response.data.text })); }, 'Suggested reply prepared. Review and edit it before choosing Queue Telegram reply.'); }}>Draft a grounded reply</button>
            {suggestions[selected.id] && <div><p>Suggestion expires {new Date(suggestions[selected.id].expires_at).toLocaleTimeString()}. No message has been sent.</p>{suggestions[selected.id].sources.map(source => <p key={source.id}><a href={source.url} target="_blank" rel="noreferrer">{source.reference}</a></p>)}<button type="button" onClick={() => { const id = selected.id; setSuggestions(value => { const next = { ...value }; delete next[id]; return next; }); setDrafts(value => ({ ...value, [id]: '' })); }}>Discard suggestion</button></div>}
            <form onSubmit={event => { event.preventDefault(); const id = selected.id; const text = drafts[id]?.trim(); if (!text) return;
              const key = replyKeys[id] || crypto.randomUUID(); setReplyKeys(value => ({ ...value, [id]: key }));
              void action(async () => { await api.post(`${base}/conversations/${id}/reply`, { text, client_key: key, ...(suggestions[id] ? { draft_id: suggestions[id].id } : {}) }, { params: { environment } }); setSuggestions(value => { const next = { ...value }; delete next[id]; return next; }); setDrafts(value => ({ ...value, [id]: '' })); setReplyKeys(value => { const next = { ...value }; delete next[id]; return next; }); }, 'Reply queued. Check its execution status for delivery.');
            }}><label>Reply through Telegram<textarea rows={3} maxLength={4096} value={drafts[selected.id] || ''} onChange={event => { const id = selected.id; setDrafts(value => ({ ...value, [id]: event.target.value })); setReplyKeys(value => { const next = { ...value }; delete next[id]; return next; }); }} disabled={busy || selected.status !== 'assigned' || selected.assignee_user_id !== data?.current_user_id} /></label><button type="submit" disabled={busy || selected.status !== 'assigned' || selected.assignee_user_id !== data?.current_user_id || !drafts[selected.id]?.trim()}>Queue Telegram reply</button></form>
          </>}
        </section> : <p>Select a conversation to read messages and manage handoff.</p>}
      </div>
    </>}
  </details>;
}
