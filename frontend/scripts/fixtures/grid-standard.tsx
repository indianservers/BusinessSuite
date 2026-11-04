import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import GridTable from "../../src/shared/data-grid/GridTable";
import SharedDataGrid from "../../src/shared/data-grid/SharedDataGrid";
import { localGridSource } from "../../src/shared/data-grid/local-source";
import type { GridColumn } from "../../src/shared/data-grid/types";
import "../../src/index.css";

type Row = { id: string; name: string; status: string };
const columns: GridColumn<Row>[] = [{ id: "name", title: "Name" }, { id: "status", title: "Status", type: "status" }];
function Fixture() {
  const [rows, setRows] = useState<Row[]>(Array.from({ length: 35 }, (_, i) => ({ id: String(i), name: `Record ${i + 1}`, status: i % 2 ? "Open" : "Done" })));
  const source = useMemo(() => localGridSource(`fixture-${JSON.stringify(rows)}`, rows, columns, r => r.id), [rows]);
  const [selected, setSelected] = useState<string[]>([]), [value, setValue] = useState("12"), [clicks, setClicks] = useState(0);
  return <main style={{ padding: 20 }}>
    <h1>Suite grid verification</h1>
    <section data-testid="shared"><SharedDataGrid gridId="test-shared" title="Work records" columns={columns} dataSource={source} getRowId={r => r.id}
      exportFormats={["csv", "clipboard"]} initialQuery={{ pageSize: 10 }}
      bulkActions={[{ id: "done", label: "Mark done", run: records => setRows(current => current.map(r => records.some(item => item.id === r.id) ? { ...r, status: "Done" } : r)) }]}/></section>
    <section data-testid="adapter"><h2>Page-owned selection</h2>
      <button onClick={() => setClicks(n => n + 1)}>Existing bulk action ({selected.length})</button><output aria-label="Action count">{clicks}</output>
      <GridTable gridId="test-adapter"><thead><tr><th><input aria-label="Existing select all" type="checkbox" checked={selected.length === 2} onChange={e => setSelected(e.target.checked ? ["a", "b"] : [])}/></th><th>Employee</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody>{["a", "b"].map(id => <tr key={id}><td><input aria-label={`Existing select ${id}`} type="checkbox" checked={selected.includes(id)} onChange={e => setSelected(s => e.target.checked ? [...s, id] : s.filter(x => x !== id))}/></td><td>Employee {id}</td><td>Active</td><td><button onClick={() => setClicks(n => n + 1)}>Edit {id}</button></td></tr>)}</tbody>
      </GridTable>
    </section>
    <section data-testid="matrix"><h2>Entry matrix</h2><form onSubmit={e => { e.preventDefault(); setClicks(n => n + 100); }}><GridTable gridId="test-matrix"><thead><tr><th>Line</th><th>Amount</th></tr></thead><tbody><tr><td>Expense</td><td><input aria-label="Amount editor" value={value} onChange={e => setValue(e.target.value)}/></td></tr></tbody></GridTable></form></section>
  </main>;
}
document.documentElement.style.cssText = "--border:220 14% 88%;--card:0 0% 100%;--background:0 0% 100%;--foreground:222 30% 15%;--muted:220 14% 96%;--muted-foreground:220 10% 45%;--primary:240 65% 55%;--primary-foreground:0 0% 100%;font-family:system-ui";
createRoot(document.getElementById("root")!).render(<MemoryRouter><QueryClientProvider client={new QueryClient()}><Fixture/></QueryClientProvider></MemoryRouter>);
