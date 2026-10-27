import { Empty } from "./EmptyState";
export function PlannedApplication({
  section,
  name,
  onBack,
}: {
  section: string;
  name?: string;
  onBack: () => void;
}) {
  return (
    <section className="pa-panel">
      <Empty
        title={name ? `${name} is on the roadmap` : "Application unavailable"}
      >
        This application has its own workspace boundary. Its tools are not
        implemented in Phase 1.
      </Empty>
      <div className="pa-planned-note">
        {section === "forms"
          ? "The existing shared form builder will be reused. No duplicate form engine has been created."
          : "Future integrations will require explicit configuration and permission checks."}
      </div>
      <button onClick={onBack}>Back to overview</button>
    </section>
  );
}
