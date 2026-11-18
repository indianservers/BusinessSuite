import { toast } from "@/hooks/use-toast";
import { api } from "@/services/api";
import { csvText, downloadBlob, transferError } from "@/shared/data-transfer/transfer";
export function exportRows(filename: string, rows: Record<string, unknown>[], format: "csv" | "xls" | "xlsx" = "csv") {
  if (!rows.length) return;
  if(format!=="csv") { const body=new FormData();body.append("file",new File([JSON.stringify(rows)],"export.json",{type:"application/json"}));body.append("format","xlsx");void api.post("/data-transfer/export/convert",body,{responseType:"blob"}).then(response=>downloadBlob(response.data,filename.replace(/\.(csv|xls|xlsx)$/i,"")+".xlsx")).catch(error=>{window.dispatchEvent(new CustomEvent("suite:export-error",{detail:transferError(error)}));toast({title:"Export failed",description:"Please try again or use CSV.",variant:"destructive"});});return; }
  downloadBlob(new Blob(["\ufeff"+csvText(rows,undefined,true)],{type:"text/csv;charset=utf-8"}),filename.endsWith(".csv")?filename:`${filename}.csv`);
}

export function exportHtmlTable(table: HTMLTableElement, filename = "table.csv") {
  const rows = Array.from(table.querySelectorAll("tr")).map((tr) =>
    Array.from(tr.querySelectorAll("th,td")).map((cell) => `"${(cell.textContent || "").trim().replace(/"/g, '""')}"`).join(",")
  );
  const blob = new Blob([rows.join("\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

