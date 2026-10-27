import type React from "react";
import type { Resource } from "../../registry";
type Props = {
  save: (event: React.FormEvent) => Promise<void>;
  editing?: Resource;
  name: string;
  description: string;
  definition: string;
  setName: (value: string) => void;
  setDescription: (value: string) => void;
  setDefinition: (value: string) => void;
  setDirty: (value: boolean) => void;
  saving: boolean;
  dirty: boolean;
  can: (permission: string) => boolean;
  move: (route: string) => void;
};
export function DraftEditor({
  save,
  editing,
  name,
  description,
  definition,
  setName,
  setDescription,
  setDefinition,
  setDirty,
  saving,
  dirty,
  can,
  move,
}: Props) {
  return (
    <form className="pa-panel pa-editor" onSubmit={save}>
      <div className="pa-section-title">
        <h2>
          {editing
            ? `Edit draft - v${editing.version}`
            : "New automation draft"}
        </h2>
        <button type="button" onClick={() => move("/power-apps/automations")}>
          Back to drafts
        </button>
      </div>
      <label>
        Name
        <input
          required
          maxLength={180}
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            setDirty(true);
          }}
        />
      </label>
      <label>
        Description
        <textarea
          maxLength={2000}
          rows={3}
          value={description}
          onChange={(e) => {
            setDescription(e.target.value);
            setDirty(true);
          }}
        />
      </label>
      <label>
        Workflow definition - JSON
        <textarea
          className="pa-code"
          spellCheck={false}
          rows={16}
          value={definition}
          onChange={(e) => {
            setDefinition(e.target.value);
            setDirty(true);
          }}
        />
      </label>
      <p className="pa-muted">
        Schema v1 supports manual, event, scheduled and webhook triggers, plus
        condition, branch, action, delay and approval nodes. Visual editing
        arrives in Phase 2. Credentials must use references.
      </p>
      <div className="pa-editor-actions">
        <button
          className="pa-primary"
          disabled={saving || (editing ? !can("edit") : !can("create"))}
        >
          {saving ? "Saving..." : "Save draft"}
        </button>
        <span>
          {dirty ? "Unsaved changes" : editing ? "Saved draft" : "Draft only"}
        </span>
      </div>
    </form>
  );
}
