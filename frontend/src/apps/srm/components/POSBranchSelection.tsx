import { useEffect, useRef, useState } from 'react';
import { defaultBranch, saveDefaultBranch } from '@/lib/default-branch';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/services/api';
import { useRecordScope } from '@/lib/record-scope';
import { switchSuiteContext } from '@/lib/switch-suite-context';
import { NativeSelect } from '@/components/ui/native-select';
import { Button } from '@/components/ui/button';
import { dealError } from '@/apps/crm/deals/deal-utils';

type Branch = {id:number; name:string; can_write:boolean; is_active?:boolean; is_deleted?:boolean};
type Context = {company_id:number; default_branch_id?:number|null; branches:Branch[]};

export default function POSBranchSelection() {
  const scope = useRecordScope(), client = useQueryClient();
  const attempted = useRef(false);
  const [remember, setRemember] = useState(true);
  const [selected,setSelected] = useState(''), [busy,setBusy] = useState(false), [error,setError] = useState('');
  const branches = useQuery({queryKey:['pos-branch-choices',scope], retry:false,
    queryFn: async ({signal}) => {
      const {data} = await api.get<Context>('/branches/context', {signal,recordCache:false,headers:{'X-Suite-Pack-Context':null}});
      if (!data || !Array.isArray(data.branches)) throw new Error('Branch choices could not be loaded.');
      return data;
    }});
  const choices = branches.data?.branches.filter(branch=>branch.can_write && branch.is_active !== false && !branch.is_deleted) || [];
  const saved = branches.data ? defaultBranch(branches.data.company_id) : null;
  const validDefault = choices.some(branch => String(branch.id) === saved) ? saved : null;
  const serverDefault = choices.find(branch => branch.id === branches.data?.default_branch_id);
  const value = selected || validDefault || (serverDefault ? String(serverDefault.id) : choices.length === 1 ? String(choices[0].id) : '');
  useEffect(() => {
    if (!validDefault || attempted.current) return;
    attempted.current = true;
    void open(false);
  }, [validDefault]);
  async function open(persist = remember) {
    if (!branches.data || !choices.some(branch=>String(branch.id) === value)) return;
    setBusy(true); setError('');
    try {
      const company = branches.data.company_id;
      const switched = await switchSuiteContext(client,company,value,'/srm/pos/terminal');
      if (switched && persist) saveDefaultBranch(company, value);
    }
    catch (error) { setError(dealError(error)); }
    finally { setBusy(false); }
  }
  return <section className="m-4 max-w-xl space-y-4 rounded-xl border bg-card p-6 text-card-foreground" aria-label="Select POS branch">
    <h1 className="text-xl font-semibold">Open POS terminal</h1>
    <p className="text-sm text-muted-foreground">Choose the branch for your sales, register and stock. Set a default to open it automatically next time.</p>
    <label className="grid gap-2 text-sm">POS branch<NativeSelect aria-label="POS branch" loading={branches.isFetching} disabled={busy || branches.isFetching || !choices.length} value={value} onChange={event=>setSelected(event.target.value)}>
      <option value="">Choose a branch</option>{choices.map(branch=><option key={branch.id} value={branch.id}>{branch.name}</option>)}
    </NativeSelect></label>
    <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={remember} onChange={event=>setRemember(event.target.checked)}/>Set this as my default branch in this browser</label>
    {branches.isSuccess && !choices.length && <p role="alert" className="text-sm">No active branch with POS write access is available. Update your branch access in Company Admin.</p>}
    {(branches.isError || error) && <p role="alert" className="text-sm text-destructive">{error || dealError(branches.error)}</p>}
    <div className="flex flex-wrap gap-2"><Button disabled={!value || busy || branches.isFetching} onClick={()=>void open()}>{busy ? 'Opening POS...' : 'Open POS'}</Button><Button variant="outline" disabled={busy || branches.isFetching} onClick={()=>void branches.refetch()}>Reload branches</Button></div>
  </section>;
}
