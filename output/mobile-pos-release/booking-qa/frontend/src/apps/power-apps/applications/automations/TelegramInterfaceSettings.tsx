import { useState } from 'react';
import { api } from '@/services/api';
import { errorMessage } from '../../api';
import type { Environment } from '../../registry';

export type TelegramConfiguration = { public_enabled: boolean; company_enabled: boolean; create_crm_records: boolean; company_user_ids: string[]; public_welcome: string; company_welcome: string };
const defaults: TelegramConfiguration = { public_enabled: true, company_enabled: true, create_crm_records: false, company_user_ids: [], public_welcome: 'Welcome! Choose Sales, Support, or Order status. Send /cancel to reset.', company_welcome: 'Company workspace: choose Create lead, Create task, Internal request or Help. Send /human for a person or /public for customer enquiries.' };

export function TelegramInterfaceSettings({ resourceId, environment, initial, editable, username }: { resourceId: number; environment: Environment; initial?: TelegramConfiguration; editable: boolean; username?: string }) {
  const [config, setConfig] = useState<TelegramConfiguration>({ ...defaults, ...initial });

  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('');
  const [failed, setFailed] = useState(false);
  return <form className="telegram-setup" onSubmit={async event => {
    event.preventDefault(); setBusy(true); setStatus(''); setFailed(false);
    try {
      const company_user_ids = config.company_user_ids;
      const response = await api.put<{ configuration: TelegramConfiguration }>(`/power-apps/automations/telegram/${resourceId}/configuration`, { ...config, company_user_ids }, { params: { environment } });
      setConfig(response.data.configuration); setStatus('Telegram configuration saved.');
    } catch (error) { setFailed(true); setStatus(errorMessage(error)); } finally { setBusy(false); }
  }}>
    <div className="telegram-interfaces">
      <fieldset disabled={!editable || busy}>
        <legend>Public interface</legend>
        <label className="telegram-checkbox"><input type="checkbox" checked={config.public_enabled} onChange={e => setConfig({ ...config, public_enabled: e.target.checked })} />Enable public enquiries</label>
        <p>Customers can submit Sales, Support and Order status enquiries. Requests appear in message history for follow-up.</p>
        <label>Public welcome message<textarea required maxLength={2000} rows={3} value={config.public_welcome} onChange={e => setConfig({ ...config, public_welcome: e.target.value })} /></label>
        <p>Open with /public or /start public.</p>
        {username && <a href={`https://t.me/${username}?start=public`} target="_blank" rel="noreferrer">Open public interface</a>}
      </fieldset>
      <fieldset disabled={!editable || busy}>
        <legend>Company interface</legend>
        <label className="telegram-checkbox"><input type="checkbox" checked={config.company_enabled} onChange={e => setConfig({ ...config, company_enabled: e.target.checked })} />Enable company workspace</label>
        <p>Linked employees can choose Create lead, Create task or Internal request. Send /human to request a person. Access is checked on every message.</p>

        <p>Company access requires a linked employee or a verified account link. Link employees in Identity linking & human handoff below.</p>
        <label>Company welcome message<textarea required maxLength={2000} rows={3} value={config.company_welcome} onChange={e => setConfig({ ...config, company_welcome: e.target.value })} /></label>
        <p>Open with /company or /start company. Choose Internal request or Help.</p>
        {username && <a href={`https://t.me/${username}?start=company`} target="_blank" rel="noreferrer">Open company interface</a>}
      </fieldset>
    </div>
    <label className="telegram-checkbox"><input type="checkbox" disabled={!editable || busy} checked={config.create_crm_records} onChange={e => setConfig({ ...config, create_crm_records: e.target.checked })} />Create CRM leads and tasks from completed requests</label>
    <p>Sales creates a lead and follow-up task. Support, Order status and internal requests create tasks. Public intake uses the bot owner’s CRM permissions; employees use their own. Enabling requires a bot branch and CRM lead/task creation permission.</p>
    {editable && <button type="submit" disabled={busy}>{busy ? 'Saving…' : 'Save interface settings'}</button>}
    {status && <p role={failed ? 'alert' : 'status'}>{status}</p>}
  </form>;
}
