import type { BotModule } from './action-bot-context';

export type WritingAction = { id: string; label: string };
export function pageWritingPath(path:string,search:string) {
  const operation=new URLSearchParams(search).get('operation');
  const prefix='/'+path.split('/')[1]+'/';
  return operation?.startsWith(prefix)?operation.split('?')[0]:path;
}
const a = (id: string, label: string): WritingAction => ({ id, label });
export const documentActions = [a('improve','Improve wording'),a('shorten','Shorten text'),a('tone','Change tone'),a('translate','Translate text'),a('extract','Extract key details')];
const client = [a('client_email','Draft client email'),a('reply','Draft reply'),a('follow_up','Draft follow-up'),a('meeting_invitation','Draft meeting invitation'),a('whatsapp','Draft WhatsApp message')];
const crm = [a('client_summary','Summarize client history'),a('proposal','Draft proposal'),a('talking_points','Prepare talking points')];
const tasks = [a('task_description','Write task description'),a('subtasks','Suggest subtasks')];
const projects = [a('project_summary','Summarize progress'),a('status_update','Draft client status update')];
const invoices = [a('invoice_email','Draft invoice email'),a('payment_reminder','Draft payment reminder'),a('overdue_reminder','Draft overdue follow-up')];
const meetings = [a('meeting_summary','Summarize meeting'),a('action_items','Extract action items'),a('meeting_follow_up','Draft meeting follow-up')];
const support = [a('ticket_summary','Summarize ticket'),a('support_reply','Draft support reply')];
const hiring = [a('job_description','Draft job description'),a('interview_questions','Suggest interview questions')];
const hr = [a('onboarding','Draft onboarding message'),a('announcement','Draft announcement'),a('policy_explanation','Explain policy')];
const purchasing = [a('supplier_enquiry','Draft supplier enquiry'),a('quotation_request','Draft quotation request'),a('purchase_order_email','Draft purchase-order email'),a('stock_delay','Draft stock-delay update')];

/** Shared route coverage includes list/detail/create pages and legacy HR URLs. */
export function pageWritingContext(path: string): { module: BotModule; actions: WritingAction[] } | null {
  if (/\/(?:settings|connectors|import-data|security|audit|logs|permissions|ai-agents|ai-assistant)(?:\/|$)/.test(path)) return null;
  const module: BotModule | undefined = /^\/crm(?:\/|$)/.test(path)?'CRM':/^\/pms(?:\/|$)/.test(path)?'PMS':/^\/srm(?:\/|$)/.test(path)?'SRM':/^\/fam(?:\/|$)/.test(path)?'FAM':/^\/hrms(?:\/|$)|^\/(?:recruitment|onboarding|engagement|helpdesk|documents|letters-certificates|employees|policies)(?:\/|$)/.test(path)?'HRMS':undefined;
  if (!module) return null;
  let actions: WritingAction[] = [];
  if (/\/(?:notes|meetings|calls|calendar|activities)(?:\/|$)/.test(path)) actions.push(...meetings);
  if (/\/(?:tasks|issues|backlog|sprints|navigator|my-work|daily-work|my-assignments)(?:\/|$)/.test(path)) actions.push(...tasks,...projects);
  if (/\/(?:tickets|helpdesk|support|knowledge-base)(?:\/|$)/.test(path)) actions.push(...support);
  if (/\/(?:invoices|invoice-drafts|collections|payment-requests|receivables|ar|billing-plans)(?:\/|$)/.test(path)) actions.push(...invoices);
  if (/\/(?:inventory|purchase-orders|purchase-bills|purchases|vendors|suppliers|sales-orders|warehouses|stock-transfers|reorder-alerts|products|items)(?:\/|$)/.test(path)) actions.push(...purchasing);
  if (/\/(?:recruitment|hiring|jobs|candidates)(?:\/|$)/.test(path)) actions.push(...hiring);
  if (/\/(?:onboarding|engagement|announcements|policies|employees|letters-certificates)(?:\/|$)/.test(path)) actions.push(...hr);
  if (/\/(?:documents|files|templates|email-templates|mail-merge-templates)(?:\/|$)/.test(path)) actions.push(...documentActions);
  if (/\/(?:messages|emails|communication-hub|communication-timeline|whatsapp|whatsapp-communication|whatsapp-ess|campaigns|greetings|send-reminders|auto-responses)(?:\/|$)/.test(path)) actions.push(...client);
  if (module==='CRM' && /\/(?:leads|contacts|accounts|companies|customers|deals|pipeline|quotes|quotations|customer-360|product-customers|potential-clients|customer-follow-ups|follow-ups)(?:\/|$)/.test(path)) actions.push(...client,...crm);
  if (module==='PMS' && (/^\/pms\/?$/.test(path)||/\/(?:projects|workspaces|reports|roadmap|timeline|dashboards)(?:\/|$)/.test(path))) actions.push(...projects,...tasks);
  if (module==='HRMS' && /^\/hrms\/?$/.test(path)) actions.push(...hr);
  if (!actions.length) return null;
  return {module,actions:Array.from(new Map(actions.map(action=>[action.id,action])).values())};
}

export type WritingSource = {text: string; title: string; recipient?: string};
const visible = (el: HTMLElement) => !!el.getClientRects().length && !el.closest('[data-ai-writing],.suite-action-bot,[data-page-work-tools],nav,aside');

/** Never harvest whole tables or hidden controls as one client's context. */
export function visibleWritingSource(target?: HTMLTextAreaElement | null): WritingSource {
  const dialog = Array.from(document.querySelectorAll<HTMLElement>('[role="dialog"]')).filter(visible).at(-1);
  const root = dialog || document.getElementById('suite-main') || document.querySelector('main');
  if (!root) return {text:'',title:''};
  const selection = window.getSelection();
  const selectedText = selection?.anchorNode && root.contains(selection.anchorNode) ? selection.toString().trim() : '';
  const selectedRows = Array.from(root.querySelectorAll<HTMLElement>('[aria-selected="true"],[data-state="selected"]')).filter(visible);
  const recordRoot = selectedRows.length === 1 ? selectedRows[0] : root;
  const recordPage=selectedRows.length===1||!!dialog||/\/[1-9]\d*(?:\/|$)/.test(window.location.pathname);
  const title = recordPage ? recordRoot.querySelector('h1,h2,[data-record-title]')?.textContent?.trim().slice(0,200) || '' : '';
  if (selectedText) return {text:selectedText.slice(0,16000),title};
  const fieldText = target?.isConnected ? target.value : '';
  const fields = Array.from(recordRoot.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>('input:not([type]),input[type="text"],input[type="email"],textarea')).filter(el=>visible(el)&&!el.readOnly&&!/search|filter|password|token|secret/i.test([el.name,el.id,el.placeholder].join(' '))).map(el=>{
    const label = el.labels?.[0]?.textContent?.trim() || el.getAttribute('aria-label') || el.placeholder || el.name;
    return el.value.trim() ? `${label || 'Details'}: ${el.value}` : '';
  }).filter(Boolean).slice(0,24);
  const editors = Array.from(recordRoot.querySelectorAll<HTMLElement>('[contenteditable="true"]')).filter(visible).map(el=>el.innerText);
  const details = Array.from(recordRoot.querySelectorAll<HTMLElement>(recordPage?'p,dl,[data-ai-context]':'[data-ai-context]')).filter(el=>visible(el)&&!el.closest('table,[role="grid"],[data-ai-writing]')).map(el=>el.innerText?.trim()).filter(Boolean).slice(0,20);
  const row = selectedRows.length === 1 ? selectedRows[0].innerText : '';
  return {title,text:Array.from(new Set([fieldText,...fields,...editors,row,...details].filter(Boolean))).join('\n').slice(0,16000)};
}
