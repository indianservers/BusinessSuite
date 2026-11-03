import { NativeSelect } from "@/components/ui/native-select";
import { ImportWizard, csvText } from "@/shared/data-transfer";
import { useEffect, useState } from "react";
import { Upload, Download } from "lucide-react";
import { api } from "@/services/api";
import { PeopleDialog } from "./DirectoryDialogs";
import { type DirectoryReference, csvEscape } from "./peopleWorkspace";
import { workspaceError } from "../../pages/workspaceTypes";
type Row = { email: string; error: string; status?: string };
function parse(text: string): Row[] {
  const lines = text
    .replace(/^\uFEFF/, "")
    .split(/\r?\n/)
    .filter((line) => line.trim());
  const header = lines[0]
    ?.toLowerCase()
    .split(",")
    .map((v) => v.trim().replace(/"/g, ""));
  const column = header?.indexOf("email") ?? -1;
  const csvRow = (line: string) => {
    const values: string[] = [];
    let value = "",
      quoted = false;
    for (let i = 0; i < line.length; i++) {
      const c = line[i];
      if (c === '"') {
        if (quoted && line[i + 1] === '"') {
          value += '"';
          i++;
        } else quoted = !quoted;
      } else if (c === "," && !quoted) {
        values.push(value);
        value = "";
      } else value += c;
    }
    values.push(value);
    return values;
  };
  const emails = (column >= 0 ? lines.slice(1) : lines).map((line) =>
    (csvRow(line)[column >= 0 ? column : 0] || "").trim().toLowerCase(),
  );
  const seen = new Set<string>();
  return emails.map((email) => {
    const error = !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
      ? "Invalid email"
      : seen.has(email)
        ? "Duplicate row"
        : "";
    seen.add(email);
    return { email, error };
  });
}
export default function DirectoryImport({
  open,
  onClose,
  reference,
}: {
  open: boolean;
  onClose: () => void;
  reference?: DirectoryReference;
}) {
  const [rows, setRows] = useState<Row[]>([]);
  const [wid, setWid] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (open) {
      setRows([]);
      setError("");
      setWid(String(reference?.workspaces.find((w) => w.can_manage)?.id || ""));
    }
  }, [open]);
  const download = () => {
    const blob = new Blob(
      [
        "Email,Error\r\n" +
          rows
            .filter((r) => r.error || r.status?.startsWith("Failed"))
            .map((r) =>
              [r.email, r.error || r.status || ""].map(csvEscape).join(","),
            )
            .join("\r\n"),
      ],
      { type: "text/csv;charset=utf-8" },
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "people-import-errors.csv";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return (
    <PeopleDialog
      open={open}
      onClose={() => {
        if (!busy) onClose();
      }}
      title="Import people"
      description="Preview invitation emails before sending. This uses existing workspace invitations and registration rules; accounts are never silently created."
    >
      <ImportWizard title="Map people to invite" label="Choose spreadsheet" confirmLabel="Prepare invitation preview" maxRows={100} maxBytes={250000} fields={[{key:"email",type:"email",required:true}]} onImport={async({rows:incoming})=>{const parsed=parse(csvText(incoming,["email"]));setRows(parsed);setError("");return {created:parsed.filter(r=>!r.error).length,message:"Emails prepared. Close this dialog, choose a workspace, then send valid invitations."};}}/>
      <label>
        Destination workspace
        <NativeSelect
          aria-label="Import workspace"
          disabled={busy}
          value={wid}
          onChange={(e) => setWid(e.target.value)}
        >
          <option value="">Choose workspace</option>
          {reference?.workspaces
            .filter((w) => w.can_manage)
            .map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
        </NativeSelect>
      </label>
      {error && (
        <p role="alert" className="pd-error">
          {error}
        </p>
      )}
      <p>
        {rows.filter((r) => !r.error).length} valid ·{" "}
        {rows.filter((r) => r.error).length} row errors ·{" "}
        {
          rows.filter(
            (r) => r.status === "Invited" || r.status === "Already invited",
          ).length
        }{" "}
        complete
      </p>
      <div className="pd-import-preview">
        {rows.map((row, index) => (
          <div key={index}>
            <span>{row.email || "Empty email"}</span>
            <small className={row.error ? "pd-error" : ""}>
              {row.error || row.status || "Ready to invite"}
            </small>
          </div>
        ))}
      </div>
      <p className="pd-scope-note">
        Role: Member. Valid recipients receive the existing invitation email.
        Authorization and provisioning rules are checked by the server.
      </p>
      <div className="pd-dialog-actions">
        <button
          className="pd-button"
          disabled={
            !rows.some((r) => r.error || r.status?.startsWith("Failed"))
          }
          onClick={download}
        >
          <Download size={14} />
          Row errors
        </button>
        <button
          className="pd-primary"
          disabled={
            busy ||
            !wid ||
            !rows.some(
              (r) =>
                !r.error &&
                !["Invited", "Already invited"].includes(r.status || ""),
            )
          }
          onClick={async () => {
            setBusy(true);
            setError("");
            try {
              const { data: pending } = await api.get<
                { email: string; status: string }[]
              >(`/project-management/workspaces/${wid}/invitations`);
              for (let i = 0; i < rows.length; i++) {
                const row = rows[i];
                if (
                  row.error ||
                  ["Invited", "Already invited"].includes(row.status || "")
                )
                  continue;
                let status = "Invited";
                try {
                  if (
                    pending.some(
                      (invite) =>
                        invite.email.toLowerCase() === row.email &&
                        invite.status === "pending",
                    )
                  )
                    status = "Already invited";
                  else
                    await api.post(
                      `/project-management/workspaces/${wid}/invitations`,
                      { email: row.email, role: "Member" },
                    );
                } catch (e) {
                  status = "Failed: " + workspaceError(e);
                }
                setRows((current) =>
                  current.map((r, index) =>
                    index === i ? { ...r, status } : r,
                  ),
                );
              }
            } catch (e) {
              setError(workspaceError(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? "Sending invitations…" : "Send valid invitations"}
        </button>
      </div>
    </PeopleDialog>
  );
}
