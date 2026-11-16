import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { MessageSquare, Send, ArrowRight, RefreshCw } from 'lucide-react';
import { api } from '@/services/api';
import { errorMessage } from '../../api';
import type { Environment } from '../../registry';
import { studioPath } from './studioApi';
import './telegram.css';
import { TelegramOperations } from './TelegramOperations';
import { TelegramInterfaceSettings, type TelegramConfiguration } from './TelegramInterfaceSettings';

type Message = { id: number; run_id: number; text: string; reply: string; sender: string; chat_id: string; enquiry_completed: boolean; state: { name?: string; topic?: string; requirement?: string }; created_at: string };
type Bot = { resource_id: number; name: string; username: string; enabled: boolean; last_polled?: string; error?: string; can_manage: boolean; messages: Message[]; configuration?: TelegramConfiguration };
type Simulation = { steps: { message: string; reply: string; stage: string }[]; sent: boolean };
const base = '/power-apps/automations/telegram';

export function TelegramAutomations({ environment, can, onCreated }: { environment: Environment; can: (permission: string) => boolean; onCreated: () => void }) {
  const [bots, setBots] = useState<Bot[]>([]);
  const [token, setToken] = useState('');
  const [name, setName] = useState('Telegram customer enquiries');
  const [showSetup, setShowSetup] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [simulation, setSimulation] = useState<Simulation>();
  const [sample, setSample] = useState('/start\nSales\nAlex\nI need a quotation for 10 units');
  const [refresh, setRefresh] = useState(0);
  const canSetup = can('create') && can('publish') && can('manage_credentials') && can('execute');
  useEffect(() => {
    let live = true;
    const load = () => api.get<{ items: Bot[] }>(`${base}/bots`, { params: { environment } }).then(response => { if (live) setBots(response.data.items); }).catch(err => { if (live) setError(errorMessage(err)); });
    void load();
    const interval = window.setInterval(() => { void load(); }, 8000);
    return () => { live = false; window.clearInterval(interval); };
  }, [environment, refresh]);
  useEffect(() => { setToken(''); setSimulation(undefined); setShowSetup(false); }, [environment]);
  async function setup() {
    setBusy(true); setError('');
    try {
      await api.post(`${base}/setup`, { name, ...(token.trim() ? { token: token.trim() } : {}) }, { params: { environment } });
      setToken(''); setShowSetup(false); setRefresh(value => value + 1); onCreated();
    } catch (err) { setError(errorMessage(err)); }
    finally { setBusy(false); }
  }
  async function toggle(bot: Bot) {
    setBusy(true); setError('');
    try {
      await api.put(`${base}/${bot.resource_id}`, { enabled: !bot.enabled }, { params: { environment } });
      setRefresh(value => value + 1); onCreated();
    } catch (err) { setError(errorMessage(err)); }
    finally { setBusy(false); }
  }
  return <section className="telegram-automations" aria-label="Telegram automations">
    <header><div><h3><Send size={20} />Telegram configuration</h3><p>One bot. A company workspace and a public enquiry interface.</p><Link to={studioPath("/power-apps/automations/telegram", environment)}>Open Telegram configuration page</Link></div>{canSetup && <button type="button" onClick={() => setShowSetup(value => !value)}>{showSetup ? 'Close setup' : 'Connect Telegram bot'}</button>}</header>
    <div className="telegram-flow"><span><MessageSquare size={17} />Message received</span><ArrowRight size={18}/><span>Check message & collect enquiry</span><ArrowRight size={18}/><span><Send size={17}/>Send Telegram reply</span></div>
    <p className="telegram-note">Sales, Support and Order status â†’ name â†’ requirement â†’ acknowledgement. Enable CRM creation in interface settings to create leads and follow-up tasks. Use /human for staff handoff.</p>
    {error && <p role="alert" className="pa-error">{error}</p>}
    {showSetup && <form className="telegram-setup" onSubmit={event => { event.preventDefault(); void setup(); }}>
      <label>Automation name<input required maxLength={180} value={name} onChange={event => setName(event.target.value)} /></label>
      <label>Telegram bot token<input type="password" autoComplete="new-password" spellCheck={false} value={token} onChange={event => setToken(event.target.value)} placeholder="Temporary server token configured · optional override" /></label>
      <p>Leave the token blank to use the temporary server token. The token is encrypted in the backend vault. Connecting enables replies to new private messages. Keep the local automation worker running.</p>
      <button type="submit" className="pa-primary" disabled={busy}>{busy ? 'Verifying botâ€¦' : 'Verify bot & enable auto-reply'}</button>
    </form>}
    <p className="telegram-note">Telegram is available now. WhatsApp and Voice AI are planned for a later version.</p>
    {bots.map(bot => <article key={bot.resource_id} className="telegram-bot">
      <header><div><h4>{bot.name}</h4><p>{bot.username ? <a href={`https://t.me/${bot.username}`} target="_blank" rel="noreferrer">@{bot.username}</a> : 'Telegram bot'} Â· {bot.enabled ? 'Enabled' : 'Paused'} Â· {bot.last_polled ? `Last checked ${new Date(bot.last_polled).toLocaleTimeString()}` : 'Waiting for local worker'}</p></div><div className="telegram-controls"><Link to={studioPath(`/power-apps/automations/${bot.resource_id}/edit`, environment)}>Open workflow</Link>{bot.can_manage && can('publish') && <button disabled={busy} type="button" onClick={() => void toggle(bot)}>{bot.enabled ? 'Pause replies' : 'Enable replies'}</button>}<button type="button" aria-label="Refresh Telegram messages" onClick={() => setRefresh(value => value + 1)}><RefreshCw size={16}/></button></div></header>
      <TelegramInterfaceSettings key={`${environment}:${bot.resource_id}`} resourceId={bot.resource_id} environment={environment} initial={bot.configuration} editable={bot.can_manage && can("publish")} username={bot.username} />
      <TelegramOperations key={`operations:${environment}:${bot.resource_id}`} resourceId={bot.resource_id} environment={environment} canManage={bot.can_manage && can("publish")} canExecute={can("execute")} />
      {bot.error && <p role="alert" className="pa-error">{bot.error}</p>}
      <details><summary>Messages & enquiries ({bot.messages.length} recent)</summary>{!bot.messages.length && <p>Send /start to the bot in Telegram to test the live automation.</p>}{bot.messages.map(message => <div className="telegram-message" key={message.id}><p><strong>{message.sender || message.chat_id}:</strong> {message.text}</p><p><strong>Planned reply:</strong> {message.reply}</p>{message.enquiry_completed && <p className="telegram-enquiry">Enquiry recorded: {message.state.topic} Â· {message.state.name} Â· {message.state.requirement}</p>}<Link to={studioPath('/power-apps/automations/executions', environment)}>Check execution #{message.run_id} for delivery status</Link></div>)}</details>
    </article>)}
    <details className="telegram-simulation"><summary>Try the enquiry scenario locally</summary><p>One message per line. This preview sends no Telegram messages.</p><label>Sample conversation<textarea rows={4} maxLength={12000} value={sample} onChange={event => setSample(event.target.value)} /></label><button type="button" disabled={busy} onClick={async () => { setBusy(true); setError(''); try { const response = await api.post<Simulation>(`${base}/simulate`, { messages: sample.split('\n').filter(Boolean).slice(0, 20) }); setSimulation(response.data); } catch (err) { setError(errorMessage(err)); } finally { setBusy(false); } }}>Run local preview</button>{simulation && <div role="status">{simulation.steps.map((step, index) => <div className="telegram-message" key={index}><p><strong>Customer:</strong> {step.message}</p><p><strong>Bot:</strong> {step.reply}</p></div>)}</div>}</details>
  </section>;
}
