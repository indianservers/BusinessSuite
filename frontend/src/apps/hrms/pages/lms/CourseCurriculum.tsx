import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import OrderedList, { moveBefore } from "@/components/interaction/OrderedList";
import MoveBoard from "@/components/interaction/MoveBoard";
type Lesson = { id: string; title: string; content: string };
type Section = { id: string; title: string; lessons: Lesson[] };
type Curriculum = { revision: number; sections: Section[] };
export default function CourseCurriculum({ courseId }: { courseId: number }) {
  const query = useQuery({
    queryKey: ["curriculum", courseId],
    queryFn: () =>
      api
        .get<Curriculum>(`/lms/courses/${courseId}/curriculum`)
        .then((r) => r.data),
  });
  const [section, setSection] = useState("");
  const [lesson, setLesson] = useState("");
  const [target, setTarget] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  async function save(sections: Section[]) {
    if (!query.data || saving) return;
    setSaving(true);
    try {
      await api.put(`/lms/courses/${courseId}/curriculum`, {
        revision: query.data.revision,
        sections,
      });
      await query.refetch();
    } catch (e) {
      await query.refetch();
      throw e;
    } finally {
      setSaving(false);
    }
  }
  const sections = query.data?.sections || [];
  async function add(kind: "section" | "lesson") {
    setError("");
    try {
      if (kind === "section") {
        await save([
          ...sections,
          { id: crypto.randomUUID(), title: section.trim(), lessons: [] },
        ]);
        setSection("");
      } else {
        const destination = target || sections[0]?.id;
        await save(
          sections.map((s) =>
            s.id === destination
              ? {
                  ...s,
                  lessons: [
                    ...s.lessons,
                    {
                      id: crypto.randomUUID(),
                      title: lesson.trim(),
                      content: "",
                    },
                  ],
                }
              : s,
          ),
        );
        setLesson("");
      }
    } catch {
      setError(
        "Could not save curriculum. Check access or refresh for newer changes.",
      );
    }
  }
  if (query.isError) return <p role="alert">Unable to load curriculum.</p>;
  if (!query.data) return <p role="status">Loading curriculum…</p>;
  return (
    <div className="space-y-3 border-t pt-3">
      <div className="flex gap-2">
        <input
          className="input min-w-0"
          aria-label="New course section"
          value={section}
          onChange={(e) => setSection(e.target.value)}
          placeholder="Section title"
        />
        <button
          type="button"
          disabled={!section.trim() || saving}
          onClick={() => void add("section")}
        >
          Add section
        </button>
      </div>
      <OrderedList
        label="Course sections"
        items={sections}
        disabled={saving}
        title={(s) => s.title}
        onReorder={save}
      />
      {!!sections.length && (
        <>
          <div className="flex flex-wrap gap-2">
            <input
              className="input min-w-0"
              aria-label="New lesson"
              value={lesson}
              onChange={(e) => setLesson(e.target.value)}
              placeholder="Lesson title"
            />
            <select
              aria-label="Lesson section"
              value={target || sections[0].id}
              onChange={(e) => setTarget(e.target.value)}
            >
              {sections.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.title}
                </option>
              ))}
            </select>
            <button
              type="button"
              disabled={!lesson.trim() || saving}
              onClick={() => void add("lesson")}
            >
              Add lesson
            </button>
          </div>
          <MoveBoard
            label="Course lessons"
            disabled={saving}
            groups={sections.map((s) => ({ id: s.id, label: s.title }))}
            items={sections.flatMap((s) =>
              s.lessons.map((l) => ({ id: l.id, label: l.title, group: s.id })),
            )}
            onMove={async ({ item, group, beforeId }) => {
              const found = sections
                .flatMap((s) => s.lessons)
                .find((l) => l.id === item.id);
              if (!found) return;
              await save(
                sections.map((s) => ({
                  ...s,
                  lessons:
                    s.id === group
                      ? moveBefore(
                          [...s.lessons.filter((l) => l.id !== item.id), found],
                          item.id,
                          beforeId,
                        )
                      : s.lessons.filter((l) => l.id !== item.id),
                })),
              );
            }}
          />
        </>
      )}
      {error && <p role="alert">{error}</p>}
    </div>
  );
}
