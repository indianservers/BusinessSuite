import { useState } from "react";
import { api } from "@/services/api";
import OrderedList from "@/components/interaction/OrderedList";
type Step = { id: number; task_name: string; order_index: number };
export default function TemplateSteps({
  template,
  refresh,
}: {
  template: { id: number; name: string; tasks: Step[] };
  refresh: () => Promise<unknown>;
}) {
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const steps = [...(template.tasks || [])].sort(
    (a, b) => a.order_index - b.order_index || a.id - b.id,
  );
  return (
    <details className="rounded-md border p-3 text-sm">
      <summary>
        {template.name} · {steps.length} steps
      </summary>
      <OrderedList
        label={`${template.name} steps`}
        items={steps}
        title={(s) => s.task_name}
        onReorder={async (ordered) => {
          try {
            await api.post(
              `/onboarding/templates/${template.id}/tasks/reorder`,
              {
                ids: ordered.map((i) => i.id),
                previous_order: steps.map((i) => i.id),
              },
            );
          } finally {
            await refresh();
          }
        }}
      />
      <div className="flex gap-2">
        <input
          aria-label={`New step for ${template.name}`}
          className="input min-w-0"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Checklist step"
        />
        <button
          type="button"
          disabled={!name.trim()}
          onClick={async () => {
            setError("");
            try {
              await api.post(`/onboarding/templates/${template.id}/tasks`, {
                task_name: name,
                order_index: steps.length
                  ? Math.max(...steps.map((s) => s.order_index)) + 1
                  : 0,
              });
              setName("");
              await refresh();
            } catch {
              setError("Could not add step. Check your access and try again.");
            }
          }}
        >
          Add step
        </button>
      </div>
      {error && <p role="alert">{error}</p>}
    </details>
  );
}
