import { useEffect, useState } from 'react';
import { api } from '@/services/api';
import { errorMessage } from '../../api';
import type { Environment } from '../../registry';

type Configuration = { enabled: boolean; provider: 'local' | 'preferred' | 'openai' | 'gemini' | 'claude'; public_context: string };
type ModelStatus = { active: boolean; description: string; engine: string };
export function TelegramAISettings({ resourceId, environment, editable }: { resourceId: number; environment: Environment; editable: boolean }) {
  const [open, setOpen] = useState(false);
  const [config, setConfig] = useState<Configuration>({ enabled: true, provider: 'local', public_context: '' });
  const [model, setModel] = useState<ModelStatus>();
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const base = `/power-apps/automations/telegram/${resourceId}/ai-configuration`;
  useEffect(() => {
    if (!open) return;
    let active = true;
    void api.get<{ configuration: Configuration; local_model: ModelStatus }>(base, { params: { environment } }).then(result => {
      if (active) { setConfig(result.data.configuration); setModel(result.data.local_model); setLoaded(true); }
    }).catch(err => { if (active) setError(errorMessage(err)); });
    return () => { active = false; };
  }, [open, base, environment]);
  return <details className="telegram-operations" onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>ActionBot AI model</summary>
    {open && <form className="telegram-setup" onSubmit={event => { event.preventDefault(); setBusy(true); setError(''); setStatus('');
      void api.put<{ configuration: Configuration }>(base, config, { params: { environment } }).then(result => { setConfig(result.data.configuration); setStatus('ActionBot AI settings saved.'); }).catch(err => setError(errorMessage(err))).finally(() => setBusy(false));
    }}>
      <p>Telegram uses the same ActionBot engine and server model settings as BusinessSuite. Free-text messages go to AI; intake commands and active human handoffs keep their existing behavior.</p>
      {error && <p role="alert">{error}</p>}{status && <p role="status">{status}</p>}
      {loaded && <>
        <label className="telegram-checkbox"><input type="checkbox" checked={config.enabled} disabled={!editable || busy} onChange={event => setConfig({ ...config, enabled: event.target.checked })} />Enable ActionBot AI replies</label>
        <label>ActionBot model source<select value={config.provider} disabled={!editable || busy} onChange={event => setConfig({ ...config, provider: event.target.value as Configuration['provider'] })}><option value="local">Trained local ActionBot model</option><option value="preferred">Existing ActionBot model preference</option><option value="openai">Configured OpenAI model</option><option value="gemini">Configured Gemini model</option><option value="claude">Configured Claude model</option></select></label>
        {model && <p role="note">Local model: {model.description}. {model.active ? 'A compatible trained release is active.' : 'The trained release is unavailable; local intent handling uses the existing retrieval and rules fallback.'}</p>}
        <p>The local model recognizes intents; it is not a generative chat model. Cloud choices use the existing enabled provider, model, credentials and data-sharing settings.</p>
        <p>Publish factual answers under Verified knowledge, with sources, approval and expiry. Public cloud replies receive only approved current facts and that public chat’s recent messages. They cannot access internal business tools. Employees use their own permissions and can review proposed actions through exact, expiring Telegram approval buttons.</p>
        {editable && <button type="submit" disabled={busy}>{busy ? 'Saving AI settings…' : 'Save ActionBot AI settings'}</button>}
      </>}
    </form>}
  </details>;
}
