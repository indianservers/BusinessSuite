import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import OrderedList from "@/components/interaction/OrderedList";
import { usePageTitle } from "@/hooks/use-page-title";
type Field = {
  id: number;
  module: string;
  label: string;
  section: string;
  field_type: string;
  display_order: number;
};
export default function CustomFieldsPage() {
  usePageTitle("Custom Fields");
  const [module, setModule] = useState("employees");
  const fields = useQuery({
    queryKey: ["hr-custom-fields", module],
    queryFn: () =>
      api
        .get<Field[]>("/custom-fields/definitions", { params: { module } })
        .then((r) => r.data),
  });
  return (
    <div className="space-y-5">
      <div>
        <h1 className="page-title">Custom Fields</h1>
        <p className="page-description">
          Arrange the shared field order for each module. Changes are saved
          immediately.
        </p>
      </div>
      <label className="flex gap-3 items-center">
        Module{" "}
        <input
          className="input max-w-xs"
          value={module}
          onChange={(e) => setModule(e.target.value)}
        />
      </label>
      {fields.isError && (
        <p role="alert">
          Unable to load field definitions. Check your access and try again.
        </p>
      )}
      {fields.isLoading ? (
        <p role="status">Loading fields…</p>
      ) : (
        <OrderedList
          label="Field order"
          items={fields.data || []}
          title={(f) => f.label}
          render={(f) => (
            <p className="text-xs text-muted-foreground">
              {f.section} · {f.field_type}
            </p>
          )}
          onReorder={async (ordered) => {
            try {
              await api.post(
                "/custom-fields/definitions/reorder",
                {
                  ids: ordered.map((f) => f.id),
                  previous_order: fields.data?.map((f) => f.id),
                },
                { params: { module } },
              );
            } finally {
              await fields.refetch();
            }
          }}
        />
      )}
    </div>
  );
}
