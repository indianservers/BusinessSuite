import { NativeSelect } from "@/components/ui/native-select";
import { Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { AiAgentConfigRow } from "@/services/aiAgentsApi";

export default function AgentConfigForm({
  row,
  onChange,
  onSave,
  saving,
}: {
  row: AiAgentConfigRow;
  onChange: (next: AiAgentConfigRow) => void;
  onSave: (row: AiAgentConfigRow) => void;
  saving?: boolean;
}) {
  const patchSetting = (key: keyof AiAgentConfigRow["setting"], value: boolean | string) => {
    onChange({ ...row, setting: { ...row.setting, [key]: value } });
  };

  return (
    <Card>
      <CardContent className="grid gap-4 p-4 lg:grid-cols-[1fr_auto] lg:items-center">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-semibold">{row.agent.name}</h3>
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">{row.agent.module}</span>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">{row.agent.description}</p>
        </div>
        <div className="grid gap-3 sm:grid-cols-4 lg:min-w-[38rem]">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={row.setting.is_enabled} onChange={(event) => patchSetting("is_enabled", event.target.checked)} />
            Enabled
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={row.setting.auto_action_enabled} onChange={(event) => patchSetting("auto_action_enabled", event.target.checked)} />
            Auto action
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={row.setting.approval_required} onChange={(event) => patchSetting("approval_required", event.target.checked)} />
            Approval required
          </label>
          <div className="flex gap-2">
            <NativeSelect
              value={row.setting.data_access_scope}
              onChange={(event) => patchSetting("data_access_scope", event.target.value)}
              className="h-9 rounded-md border bg-background px-2 text-sm"
            >
              <option value="own_records">Own records</option>
              <option value="team">Team</option>
              <option value="company">Company</option>
            </NativeSelect>
            <Button type="button" size="sm" onClick={() => onSave(row)} disabled={saving}>
              <Save className="h-4 w-4" />
              Save
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

