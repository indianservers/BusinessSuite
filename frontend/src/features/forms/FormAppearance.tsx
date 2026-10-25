import { defaultSettings, type Definition, type FormSettings } from "./formsTypes";

/** Shared design controls: the canvas and public renderer read the same settings. */
export default function FormAppearance({draft, edit}: {draft: Definition; edit: (value: Definition) => void}) {
  const settings = draft.settings;
  const patch = (value: Partial<FormSettings>) => edit({...draft, settings: {...defaultSettings, ...settings, ...value}});
  return <div className="form-appearance-controls">
    <label>Columns<select value={settings?.columns || 1} onChange={e => patch({columns: Number(e.target.value) as 1 | 2 | 3})}>
      <option value={1}>One · spacious</option><option value={2}>Two · balanced</option><option value={3}>Three · compact</option>
    </select></label>
    <label>Canvas style<select value={settings?.surface || "soft"} onChange={e => patch({surface: e.target.value as FormSettings["surface"]})}>
      <option value="minimal">Minimal</option><option value="soft">Soft tint</option><option value="gradient">Gradient</option>
    </select></label>
    <label>Brand color<input type="color" value={draft.accent} onChange={e => edit({...draft, accent:e.target.value})} /></label>
    <label className="form-choice"><input type="checkbox" checked={!!settings?.intro_enabled} onChange={e => patch({intro_enabled:e.target.checked})} />Introduction panel</label>
    {settings?.intro_enabled && <>
      <label>Badge<input maxLength={80} value={settings.intro_badge ?? "Build your future"} onChange={e => patch({intro_badge:e.target.value})} /></label>
      <label>Headline<textarea maxLength={200} value={settings.intro_title ?? "Your next chapter starts here."} onChange={e => patch({intro_title:e.target.value})} /></label>
      <label>Introduction<textarea maxLength={1000} value={settings.intro_text ?? "Share your details and take the first step."} onChange={e => patch({intro_text:e.target.value})} /></label>
      <small>The introduction is hidden on phones so the form comes first.</small>
    </>}
  </div>;
}
