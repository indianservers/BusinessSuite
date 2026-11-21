import { useDeferredValue, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { NativeSelect } from "@/components/ui/native-select";
import { useRecordScope } from "@/lib/record-scope";
import { api } from "@/services/api";
import { matchesCategory } from "@/shared/employee-category-taxonomy";
import { catalogError } from "./api";

export type CatalogProvider = {
  provider_resource_id: number;
  employee_id: number;
  employee_name: string;
  provider_name: string;
  work_categories?: string[];
  eligibility_revision?: number;
};

export type StaffDraft = { provider: CatalogProvider; active: boolean };

export default function CatalogServiceStaff({ branchId, assigned, changes, categories, onChange }: {
  branchId?: number;
  assigned: CatalogProvider[];
  changes: StaffDraft[];
  categories: string[];
  onChange: (changes: StaffDraft[]) => void;
}) {
  const scope = useRecordScope();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState("");
  const searchTerm = useDeferredValue(search.trim());
  const providers = useQuery({
    queryKey: ["catalog-service-staff", scope, branchId, searchTerm],
    enabled: open && !!branchId,
    retry: false,
    queryFn: ({ signal }) => api.get<{ providers: CatalogProvider[]; has_more: boolean }>("/srm/service-checkout/options/providers", {
      headers: { "X-Suite-Branch": String(branchId) },
      params: { search: searchTerm },
      signal,
      recordCache: false,
    }).then(response => response.data),
  });
  const visible = [
    ...assigned,
    ...changes.filter(change => change.active).map(change => change.provider),
  ];
  const choices = (providers.data?.providers ?? []).filter(provider =>
    !visible.some(item => item.provider_resource_id === provider.provider_resource_id) &&
    (!categories.length || categories.some(category => matchesCategory(provider.work_categories, category))),
  );
  const candidate = choices.find(provider => String(provider.provider_resource_id) === selected);
  const toggle = (provider: CatalogProvider) => {
    const id = provider.provider_resource_id;
    const pending = changes.find(change => change.provider.provider_resource_id === id);
    onChange(pending
      ? changes.filter(change => change !== pending)
      : [...changes, { provider, active: false }]);
  };

  return <section className="sc-section" aria-label="Individual employees">
    <header><div><h3>Individual employees</h3></div>
      <button type="button" disabled={!branchId} onClick={() => setOpen(value => !value)} aria-expanded={open}>
        {open ? "Close employee picker" : "Map an employee"}
      </button>
    </header>
    {visible.map(provider => {
      const pending = changes.find(change => change.provider.provider_resource_id === provider.provider_resource_id);
      const willRemove = pending?.active === false;
      return <div key={provider.provider_resource_id} className="sc-preview-line">
        <span>{provider.employee_name}{pending && <small>{willRemove ? " (pending removal)" : " (pending assignment)"}</small>}</span>
        <button type="button" disabled={!pending && changes.length >= 100} aria-label={`${willRemove ? "Keep" : "Remove"} ${provider.employee_name}`} onClick={() => toggle(provider)}>
          {willRemove ? "Keep" : "Remove"}
        </button>
      </div>;
    })}
    {changes.length >= 100 && <p className="sc-muted">Save these changes before mapping more employees.</p>}
    {!branchId && <p className="sc-muted">Select one branch to map individual employees.</p>}
    {open && branchId ? <div className="sc-form-grid">
      <label>Find employees<input maxLength={100} value={search} onChange={event => {
        setSelected("");
        setSearch(event.target.value);
      }}/></label>
      <label>Employee<NativeSelect aria-label="Employee to map" value={candidate ? selected : ""} loading={providers.isFetching}
        error={providers.isError} onChange={event => setSelected(event.target.value)}>
        <option value="">Choose employee</option>
        {choices.map(provider => <option key={provider.provider_resource_id} value={provider.provider_resource_id}>
          {provider.employee_name} ({provider.provider_name})
        </option>)}
      </NativeSelect></label>
      <button type="button" disabled={!candidate || providers.isFetching || changes.length >= 100} onClick={() => {
        if (!candidate) return;
        onChange([...changes, { provider: candidate, active: true }]);
        setSelected("");
      }}>Add employee</button>
      {providers.data?.has_more && <p className="sc-muted">Search by name to find more employees.</p>}
      {providers.isSuccess && !choices.length && <p className="sc-muted">No appointment providers in this branch match the search and selected categories.</p>}
      {providers.isError && <p role="alert">{catalogError(providers.error)} <button type="button" onClick={() => void providers.refetch()}>Retry</button></p>}
    </div> : null}
  </section>;
}
