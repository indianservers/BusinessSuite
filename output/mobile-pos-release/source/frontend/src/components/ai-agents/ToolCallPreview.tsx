import { ChevronDown, ChevronRight, Wrench } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";

export default function ToolCallPreview({ toolCalls = [] }: { toolCalls?: Array<Record<string, unknown>> }) {
  const [expanded, setExpanded] = useState(false);
  if (!toolCalls.length) return null;

  return (
    <div className="rounded-lg border border-dashed bg-muted/30 p-3">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-3 text-left"
        onClick={() => setExpanded((value) => !value)}
      >
        <span className="inline-flex items-center gap-2 text-sm font-medium">
          <Wrench className="h-4 w-4" />
          {toolCalls.length} backend tool call{toolCalls.length === 1 ? "" : "s"}
        </span>
        {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
      </button>
      {expanded ? (
        <div className="mt-3 space-y-2">
          {toolCalls.map((call, index) => (
            <div key={index} className="rounded-md border bg-background p-3 text-xs">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <Badge variant="outline">{String(call.tool_name || call.name || `tool_${index + 1}`)}</Badge>
                {call.module ? <Badge variant="secondary">{String(call.module)}</Badge> : null}
              </div>
              <pre className="max-h-44 overflow-auto whitespace-pre-wrap">{JSON.stringify(call, null, 2)}</pre>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-2 text-xs text-muted-foreground">Tool details are collapsed by default to avoid exposing raw backend data.</p>
      )}
    </div>
  );
}

