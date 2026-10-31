import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import OrderedList, { moveBefore } from "@/components/interaction/OrderedList";
import MoveBoard from "@/components/interaction/MoveBoard";
type Section = { id: number; title: string };
type Placement = { id: number; field_id: number; section_id: number | null };
type Layout = {
  sections: Section[];
  fields: Placement[];
  arrange_version: string;
};
export default function LayoutArrangement({ layoutId }: { layoutId: number }) {
  const [open, setOpen] = useState(false);
  const query = useQuery({
    queryKey: ["layout-arrange", layoutId],
    enabled: open,
    queryFn: () =>
      api.get<Layout>(`/customization/layouts/${layoutId}`).then((r) => r.data),
  });
  const definitions = useQuery({
    queryKey: ["layout-field-labels"],
    enabled: open,
    queryFn: () =>
      api
        .get<{
          items: { id: number; field_label: string }[];
        }>("/customization/fields")
        .then((r) => r.data.items),
  });
  async function save(sections: Section[], fields: Placement[]) {
    try {
      await api.post(`/customization/layouts/${layoutId}/arrange`, {
        version: query.data?.arrange_version,
        section_ids: sections.map((s) => s.id),
        fields: fields.map((f) => ({ id: f.id, section_id: f.section_id })),
      });
    } finally {
      await query.refetch();
    }
  }
  return (
    <details
      className="w-full"
      open={open}
      onToggle={(e) => setOpen(e.currentTarget.open)}
    >
      <summary>Arrange sections and fields</summary>
      {query.isError && <p role="alert">Unable to load layout.</p>}
      {open && query.data && (
        <div className="space-y-4 pt-3">
          <OrderedList
            label="Page sections"
            items={query.data.sections}
            title={(s) => s.title}
            onReorder={(ordered) => save(ordered, query.data!.fields)}
          />
          <MoveBoard
            label="Layout fields"
            groups={[
              { id: "root", label: "No section" },
              ...query.data.sections.map((s) => ({
                id: String(s.id),
                label: s.title,
              })),
            ]}
            items={query.data.fields.map((f) => ({
              id: f.id,
              label:
                definitions.data?.find((d) => d.id === f.field_id)
                  ?.field_label || `Field ${f.field_id}`,
              group: f.section_id ? String(f.section_id) : "root",
            }))}
            onMove={async ({ item, group, beforeId }) => {
              const fields = moveBefore(
                query.data!.fields.map((f) =>
                  f.id === item.id
                    ? {
                        ...f,
                        section_id: group === "root" ? null : Number(group),
                      }
                    : f,
                ),
                item.id,
                beforeId,
              );
              await save(query.data!.sections, fields);
            }}
          />
        </div>
      )}
    </details>
  );
}
