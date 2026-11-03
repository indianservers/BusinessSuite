// Browser acceptance fixture; not an application route.
import React, {useRef, useState} from "react";
import {createRoot} from "react-dom/client";
import {NativeSelect} from "../src/components/ui/native-select";
import {Select, SelectContent, SelectItem, SelectTrigger, SelectValue} from "../src/components/ui/select";
import {ActionToolbar} from "../src/components/actions";
import CompactActions from "../src/components/actions/CompactActions";
import {savedWithUndo} from "../src/components/actions/undo-feedback";
import {Button} from "../src/components/ui/button";
import {Toaster} from "../src/components/ui/toaster";
import {useAuthStore} from "../src/store/authStore";
import {BrowserRouter} from "react-router-dom";
import RecordActions from "../src/apps/project-management/components/RecordActions";
import {Dialog, DialogContent, DialogTitle} from "../src/components/ui/dialog";
import "../src/index.css";
useAuthStore.setState({user: {id: 12, role: "admin", email: "qa@example.com", is_superuser: true}});
function DialogAction() {
  const [open, setOpen] = useState(false), [draft, setDraft] = useState("");
  return <><Button type="button" onClick={() => setOpen(true)}>Detailed edit</Button><Dialog open={open} onOpenChange={setOpen}><DialogContent><DialogTitle>Detailed editor</DialogTitle><input aria-label="Dialog draft" value={draft} onChange={event => setDraft(event.target.value)}/><Button type="button" onClick={() => setOpen(false)}>Finish editing</Button></DialogContent></Dialog></>;
}
function Harness() {
  const [value, setValue] = useState(""), [multi, setMulti] = useState<string[]>([]), [radix, setRadix] = useState(""), [canEdit, setCanEdit] = useState(true), [done, setDone] = useState(false), [deleted, setDeleted] = useState(false), [submitted, setSubmitted] = useState(""), [selected, setSelected] = useState(false), [count, setCount] = useState(0);
  const native = useRef<HTMLSelectElement>(null);
  const options = Array.from({length: 14}, (_, i) => ({value: String(i + 1), label: `Choice ${i + 1}`}));
  return <main className="space-y-6 p-4">
    <ActionToolbar label="Suite policy" actions={[
      {id: "start", kind: "start", label: "Start", prominent: true, primary: true, available: canEdit && !done, onSelect: () => setDone(true)},
      {id: "view", kind: "view", prominent: true, primary: true},
      {id: "copy", kind: "copy", prominent: true},
      {id: "export", kind: "download", prominent: true},
      {id: "delete", kind: "delete", available: canEdit, danger: true, confirm: {title: "Delete record?", description: "Review this destructive operation."}, onSelect: () => setDeleted(true)},
    ]}/>
    <p role="status">{deleted ? "Record deleted" : "Record retained"}</p>
    <Button onClick={() => setCanEdit(!canEdit)}>Toggle permission</Button>
    <form onSubmit={event => {event.preventDefault(); setSubmitted(String(new FormData(event.currentTarget).get("destination")));}} className="space-y-3">
      <label htmlFor="destination">Destination</label>
      <NativeSelect id="destination" aria-label="Destination" name="destination" ref={native} value={value} onChange={event => setValue(event.target.value)} className="h-11 w-full rounded border">
        <option value="">Choose destination</option>{options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}<optgroup label="Restricted" disabled><option value="blocked">Unavailable destination</option></optgroup>
      </NativeSelect>
      <CompactActions aria-label="Compact form actions">
        <Button type="button" variant="outline">Inspect</Button><Button type="button" variant="outline">Copy</Button><Button type="button" variant="outline">Download</Button><Button type="submit">Submit form</Button><Button type="submit" variant="outline">Submit from More</Button><DialogAction/>
      </CompactActions>
    </form>
    <output aria-label="Submitted value">{submitted}</output>
    <NativeSelect aria-label="Multiple destinations" multiple value={multi} onChange={event => setMulti(Array.from(event.currentTarget.selectedOptions, option => option.value))} className="w-full rounded border">{options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</NativeSelect>
    <output aria-label="Multiple values">{multi.join(",")}</output>
    <Select value={radix} onValueChange={setRadix} recentKey="test-radix"><SelectTrigger aria-label="Radix destination"><SelectValue placeholder="Choose"/></SelectTrigger><SelectContent>{options.map(option => <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>)}</SelectContent></Select>
    <label><input type="checkbox" checked={selected} onChange={event => setSelected(event.target.checked)}/>Select record</label>
    {selected && <ActionToolbar label="Bulk actions" actions={[{id: "assign", kind: "assign", prominent: true}, {id: "delete", kind: "delete", danger: true}]}/>}
    <Button onClick={() => {setCount(1); savedWithUndo("Value saved", async () => {setCount(0);});}}>Save simple change</Button><output aria-label="Saved count">{count}</output>
    <Toaster/>
  </main>;
}
function RecordHarness() {
  return <><RecordActions record={{id: 7, title: "Undo task", status: "To Do", priority: "Medium", project_id: 1}} canEdit>{menu => <div className="p-4">Undo task {menu}</div>}</RecordActions><Toaster/></>;
}
createRoot(document.getElementById("root")!).render(<BrowserRouter>{new URLSearchParams(location.search).has("record") ? <RecordHarness/> : <Harness/>}</BrowserRouter>);
