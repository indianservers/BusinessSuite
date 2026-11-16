import { useState } from 'react';
import { api } from '@/services/api';
import { errorMessage } from '../../api';
import type { Environment } from '../../registry';

export type TelegramAudience = 'public' | 'company' | 'shared';
export type TelegramConfiguration = { audience?: TelegramAudience; public_enabled: boolean; company_enabled: boolean; create_crm_records: boolean; company_user_ids: string[]; public_welcome: string; company_welcome: string };
const defaults: TelegramConfiguration = { public_enabled: true, company_enabled: true, create_crm_records: false, company_user_ids: [], public_welcome: 'Welcome! Choose Sales, Support, or Order status. Send /cancel to reset.', company_welcome: 'Company workspace: choose Create lead, Create task, Internal request or Help. Send /human for a person.' };

export function TelegramInterfaceSettings({ resourceId, environment, initial, editable, username, onSaved }: { resourceId: number; environment: Environment; initial?: TelegramConfiguration; editable: boolean; username?: string; onSaved?: (configuration: TelegramConfiguration) => void }) {
  const [config, setConfig] = useState<TelegramConfiguration>({ ...defaults, ...initial, audience: initial?.audience || 'shared' });
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('');
  const [failed, setFailed] = useState(false);
  return <form className="telegram-setup" onSubmit={async event => {
    event.preventDefault(); setStatus(''); setFailed(false);
    if (config.audience === 'shared') { setFailed(true); setStatus('Choose Public customer bot or Company employee bot before saving.'); return; }
    setBusy(true);
    try {
      const payload = { ...config, public_enabled: config.audience === 'public', company_enabled: config.audience === 'company' };
      const response = await api.put<{ configuration: TelegramConfiguration }>(`/power-apps/automations/telegram/${resourceId}/configuration`, payload, { params: { environment } });
      setConfig(response.data.configuration); onSaved?.(response.data.configuration); setStatus('Telegram configuration saved.');
    } catch (error) { setFailed(true); setStatus(errorMessage(error)); } finally { setBusy(false); }
  }}>
    <label>Bot purpose<select disabled={!editable || busy} value={config.audience} onChange={event => setConfig({ ...config, audience: event.target.value as TelegramAudience })}>
      {config.audience === 'shared' && <option value="shared" disabled>Legacy shared bot — choose a dedicated purpose</option>}
      <option value="public">Public customer bot</option>{initial?.audience === 'company' && <option value="company">Company employee bot</option>}
    </select></label>
    {initial?.audience === 'shared' || !initial?.audience ? <p>This existing bot still serves both audiences. Select its dedicated purpose and save to migrate it. The other audience needs a separate Telegram bot and token.</p> : <p>Each Telegram bot serves one audience. Use a different BotFather token for the other bot.</p>}
    {initial?.audience !== 'company' && <p>For an employee workspace, choose Connect company employee bot above and supply its separate BotFather token. This existing customer bot cannot be promoted to a company bot.</p>}
    <div className="telegram-interfaces">
      {config.audience !== 'company' && <fieldset disabled={!editable || busy}>
        <legend>Public customer bot</legend>
        <p>Customers can submit Sales, Support and Order status enquiries. Verify a customer link before viewing private account information.</p>
        <label>Public welcome message<textarea required maxLength={2000} rows={3} value={config.public_welcome} onChange={event => setConfig({ ...config, public_welcome: event.target.value })} /></label>
        <p>Customers open this bot and send /start. Send /human for staff support.</p>
        {username && <a href={`https://t.me/${username}?start=public`} target="_blank" rel="noreferrer">Open public customer bot</a>}
      </fieldset>}
      {config.audience !== 'public' && <fieldset disabled={!editable || busy}>
        <legend>Company employee bot</legend>
        <p>Linked employees can choose Create lead, Create task or Internal request. Current BusinessSuite permissions are checked on every message.</p>
        <p>Link employees in Identity linking & human handoff below. Employees open this bot and send /start.</p>
        <label>Company welcome message<textarea required maxLength={2000} rows={3} value={config.company_welcome} onChange={e => setConfig({ ...config, company_welcome: e.target.value })} /></label>
        {username && <a href={`https://t.me/${username}?start=company`} target="_blank" rel="noreferrer">Open company employee bot</a>}
      </fieldset>}
    </div>
    <label className="telegram-checkbox"><input type="checkbox" disabled={!editable || busy} checked={config.create_crm_records} onChange={e => setConfig({ ...config, create_crm_records: e.target.checked })} />Create CRM leads and tasks from completed requests</label>
    <p>{config.audience === 'company' ? 'Employees create CRM records using their own permissions.' : 'Public intake uses the bot owner’s CRM permissions.'} Enabling requires a bot branch and CRM lead/task creation permission.</p>
    {editable && <button type="submit" disabled={busy}>{busy ? 'Saving…' : 'Save interface settings'}</button>}
    {status && <p role={failed ? 'alert' : 'status'}>{status}</p>}
  </form>;
}
