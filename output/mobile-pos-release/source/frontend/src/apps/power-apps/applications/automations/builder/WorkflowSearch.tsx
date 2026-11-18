import { useMemo, useState } from "react";
import { Search, X } from "lucide-react";
import type { WorkflowGraph } from "./types";
export function WorkflowSearch({
  graph,
  onSelect,
  onClose,
}: {
  graph: WorkflowGraph;
  onSelect: (id: string) => void;
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");
  const matches = useMemo(
    () =>
      graph.nodes.filter((n) =>
        `${n.label} ${n.type} ${n.id} ${n.description}`
          .toLowerCase()
          .includes(query.toLowerCase()),
      ),
    [graph.nodes, query],
  );
  return (
    <section className="as-workflow-search" aria-label="Workflow search">
      <header>
        <Search size={15} />
        <input
          autoFocus
          aria-label="Search workflow nodes"
          placeholder="Find a step by name, type or ID"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button aria-label="Close workflow search" onClick={onClose}>
          <X size={16} />
        </button>
      </header>
      <div>
        {matches.slice(0, 100).map((n) => (
          <button key={n.id} onClick={() => onSelect(n.id)}>
            <strong>{n.label}</strong>
            <small>
              {n.type} · {n.disabled ? "Disabled" : n.id}
            </small>
          </button>
        ))}
        {!matches.length && <p>No matching steps.</p>}
        {matches.length > 100 && (
          <p>Showing 100 results. Refine your search.</p>
        )}
      </div>
    </section>
  );
}
