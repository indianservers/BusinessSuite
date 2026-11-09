import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import OrderedList, { moveBefore } from "@/components/interaction/OrderedList";
import MoveBoard from "@/components/interaction/MoveBoard";
import { useMobile } from "@/components/mobile/useMobile";
import { useRecordDraft } from "@/hooks/use-record-autosave";
import { useAuthStore } from "@/store/authStore";
import { selectedBranch } from "@/lib/branch-context";
import { AlertDialog, AlertDialogTrigger, AlertDialogContent, AlertDialogTitle, AlertDialogDescription, AlertDialogCancel, AlertDialogAction } from "@/components/ui/alert-dialog";
type Lesson = { id: string; title: string; content: string };
type Section = { id: string; title: string; lessons: Lesson[] };
type Curriculum = { revision: number; sections: Section[] };
type CurriculumDraft = { section: string; lesson: string; target: string };
const blankDraft = (): CurriculumDraft => ({ section: "", lesson: "", target: "" });
function browserContext() {
  try { return [sessionStorage.getItem("suite-tenant"), sessionStorage.getItem("suite-organization"), selectedBranch()]; }
  catch { return []; }
}
function phoneScope(courseId: number) {
  const actor = useAuthStore.getState().user;
  return JSON.stringify([courseId, actor?.id, actor?.employee_id, actor?.role, actor?.is_superuser, actor?.access, ...browserContext()]);
}
export default function CourseCurriculum({ courseId }: { courseId: number }) {
  const phone = useMobile(480);
  const actor = useAuthStore(state => state.user);
  const [, refreshContext] = useState(0);
  useEffect(() => {
    if (!phone) return;
    const changed = () => refreshContext(value => value + 1);
    const events = ["suite:organization-changed", "suite:branch-changed", "suite:record-access-changed"];
    events.forEach(name => window.addEventListener(name, changed));
    return () => events.forEach(name => window.removeEventListener(name, changed));
  }, [phone]);
  const scope = phone ? phoneScope(courseId) : "";
  return <CurriculumEditor key={phone ? scope : "desktop"} courseId={courseId} phone={phone} scope={scope} keepDraft={phone && !!actor?.id} />;
}
function CurriculumEditor({ courseId, phone, scope, keepDraft }: { courseId: number; phone: boolean; scope: string; keepDraft: boolean }) {
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: phone ? ["curriculum", courseId, scope] : ["curriculum", courseId],
    queryFn: () =>
      api
        .get<Curriculum>(`/lms/courses/${courseId}/curriculum`)
        .then((r) => r.data),
  });
  const [draft, setDraft] = useState<CurriculumDraft>(blankDraft);
  const { section, lesson, target } = draft;
  const setSection = (section: string) => setDraft(value => ({ ...value, section }));
  const setLesson = (lesson: string) => setDraft(value => ({ ...value, lesson }));
  const setTarget = (target: string) => setDraft(value => ({ ...value, target }));
  const draftStorage = useRecordDraft(`hrms-lms-curriculum:${scope}`, draft, saved => setDraft({
    section: typeof saved?.section === "string" ? saved.section : "",
    lesson: typeof saved?.lesson === "string" ? saved.lesson : "",
    target: typeof saved?.target === "string" ? saved.target : "",
  }), keepDraft);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  async function refreshAfterSave() {
    if (phone && scope !== phoneScope(courseId)) {
      await qc.invalidateQueries({ queryKey: ["curriculum", courseId, scope], exact: true, refetchType: "none" });
      return;
    }
    await query.refetch();
  }
  async function save(sections: Section[]) {
    if (!query.data || saving) return;
    setSaving(true);
    try {
      await api.put(`/lms/courses/${courseId}/curriculum`, {
        revision: query.data.revision,
        sections,
      });
      await refreshAfterSave();
    } catch (e) {
      await refreshAfterSave();
      throw e;
    } finally {
      setSaving(false);
    }
  }
  const sections = query.data?.sections || [];
  const invalidTarget = phone && !!target && !sections.some(item => item.id === target);
  async function add(kind: "section" | "lesson") {
    setError("");
    try {
      if (kind === "section") {
        await save([
          ...sections,
          { id: crypto.randomUUID(), title: section.trim(), lessons: [] },
        ]);
        if (keepDraft) draftStorage.persist({ ...draft, section: "" });
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
        if (keepDraft) draftStorage.persist({ ...draft, lesson: "" });
        setLesson("");
      }
    } catch {
      setError(
        "Could not save curriculum. Check access or refresh for newer changes.",
      );
    }
  }
  if (query.isError) return <p role="alert">Unable to load curriculum.{phone && <Button type="button" variant="outline" onClick={() => void query.refetch()}>Retry curriculum</Button>}</p>;
  if (!query.data) return <p role="status">Loading curriculum…</p>;
  return (
    <div className="hrms-lms-curriculum space-y-3 border-t pt-3">
      {keepDraft && (section || lesson || target) && <div className="flex flex-wrap items-center gap-2">
        <p role={draftStorage.status === "unavailable" ? "alert" : "status"} className="text-sm text-muted-foreground">{draftStorage.status === "unavailable" ? "Draft could not be stored. Keep this page open to retain your titles." : "Draft kept for this browser tab."}</p>
        <AlertDialog><AlertDialogTrigger asChild><Button type="button" variant="outline" disabled={saving}>Discard curriculum draft</Button></AlertDialogTrigger><AlertDialogContent><AlertDialogTitle>Discard curriculum draft?</AlertDialogTitle><AlertDialogDescription>Unsaved section and lesson titles and the selected destination will be cleared. Published curriculum stays unchanged.</AlertDialogDescription><AlertDialogCancel>Continue editing</AlertDialogCancel><AlertDialogAction disabled={saving} onClick={() => { draftStorage(); setDraft(blankDraft()); }}>Discard draft</AlertDialogAction></AlertDialogContent></AlertDialog>
      </div>}
      <div className="hrms-lms-section-entry flex gap-2">
        <input
          className="input min-w-0"
          aria-label="New course section"
          value={section}
          disabled={phone && saving}
          onChange={(e) => setSection(e.target.value)}
          placeholder="Section title"
        />
        <Button variant="default"
          type="button"
          disabled={!section.trim() || saving}
          onClick={() => void add("section")}
        >
          Add section
        </Button>
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
              disabled={phone && saving}
              onChange={(e) => setLesson(e.target.value)}
              placeholder="Lesson title"
            />
            <NativeSelect loading={query.isFetching} error={query.isError}
              aria-label="Lesson section"
              disabled={phone && saving}
              value={invalidTarget ? "" : target || sections[0].id}
              onChange={(e) => setTarget(e.target.value)}
            >
              {invalidTarget && <option value="" disabled>Choose a section</option>}
              {sections.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.title}
                </option>
              ))}
            </NativeSelect>
            <Button variant="default"
              type="button"
              disabled={!lesson.trim() || saving || invalidTarget}
              onClick={() => void add("lesson")}
            >
              Add lesson
            </Button>
          </div>
          {invalidTarget && <p role="alert">The selected section is no longer available. Choose a section before adding the lesson.</p>}
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
