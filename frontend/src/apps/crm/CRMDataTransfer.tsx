import { useSearchParams } from "react-router-dom";
import { refreshPageData } from "@/lib/page-refresh";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { crmApi, type CRMApiRecord } from "./api";
import {
  ImportWizard,
  DataExportButton,
  type TransferField,
  type ImportResult,
} from "@/shared/data-transfer";
import { leadsApi } from "./leads/api";

export function LeadSpreadsheetImport({
  autoOpen,
  onClose,
  onImported,
}: {
  autoOpen?: boolean;
  onClose?: () => void;
  onImported?: () => void;
}) {
  const qc = useQueryClient();
  return (
    <ImportWizard
      title="Import leads"
      autoOpen={autoOpen}
      onClose={onClose}
      fields={async () =>
        (await api.get<TransferField[]>("/crm/lead-management/excel/fields"))
          .data
      }
      onImport={async ({ file }) => {
        const { data: preview } = await leadsApi.previewImport(file);
        if (preview.errors.length)
          return {
            created: 0,
            errors: preview.errors.map((e) => ({ ...e, row: e.row - 1 })),
          };
        const { data } = await leadsApi.import(preview.rows);
        qc.invalidateQueries({ queryKey: ["crm"] });
        onImported?.();
        return {
          created: data.created,
          message: `${data.created} leads imported. ${data.skipped.length} duplicates skipped.`,
        };
      }}
    />
  );
}
export default function CRMDataTransfer({
  entity,
  onImported,
  importLabel,
  exportLabel,
  importOnly,
}: {
  entity: string;
  onImported?: () => void;
  importLabel?: string;
  exportLabel?: string;
  importOnly?: boolean;
}) {
  const qc = useQueryClient();
  return (
    <>
      <ImportWizard
        title={`Import ${entity.replace(/-/g, " ")}`}
        label={importLabel}
        fields={async () =>
          (await api.get<TransferField[]>(`/crm/${entity}/import-fields`)).data
        }
        onImport={async ({ rows }) => {
          const { data } = await crmApi.importRows<ImportResult>(
            entity,
            rows as CRMApiRecord[],
          );
          if (!data.errors?.length) {
            await refreshPageData(qc);
            onImported?.();
          }
          return data;
        }}
      />
      {!importOnly && (
        <DataExportButton
          label={exportLabel}
          filename={entity}
          description={`All accessible ${entity.replace(/-/g, " ")}. Existing export limits and permissions apply.`}
          load={async () => (await crmApi.exportEntity(entity)).data}
        />
      )}
    </>
  );
}
export function CRMTransferHub() {
  const [params] = useSearchParams();
  const [entity, setEntity] = useState(() => {
      const requested = params.get("entity") || "contacts";
      return [
        "contacts",
        "leads",
        "companies",
        "deals",
        "products",
        "services",
        "tasks",
      ].includes(requested)
        ? requested
        : "contacts";
    }),
    [revision, setRevision] = useState(0);
  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">Import & Export</h1>
        <p className="page-description">
          Bring your spreadsheet into CRM. Match columns, review your rows, then
          import.
        </p>
      </div>
      <section className="rounded-xl border bg-card p-6 space-y-5">
        <label className="block text-sm font-medium">
          What data are you working with?
          <select
            className="mt-2 block w-full max-w-md rounded-md border bg-background p-3"
            value={entity}
            onChange={(e) => setEntity(e.target.value)}
          >
            {[
              ["contacts", "Contacts"],
              ["leads", "Leads"],
              ["companies", "Customers / Companies"],
              ["deals", "Deals"],
              ["products", "Products"],
              ["services", "Services"],
              ["tasks", "Tasks"],
            ].map(([value, name]) => (
              <option key={value} value={value}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <div key={`${entity}:${revision}`} className="flex flex-wrap gap-3">
          {entity === "leads" ? (
            <>
              <LeadSpreadsheetImport
                onImported={() => setRevision((v) => v + 1)}
              />
              <DataExportButton
                filename="leads.xlsx"
                load={async () => (await leadsApi.export({})).data}
              />
            </>
          ) : (
            <CRMDataTransfer entity={entity} />
          )}
        </div>
        <p className="text-sm text-muted-foreground">
          Excel and CSV uploads are supported. Download a template in the import
          dialog, or use your own column headings. Existing records are
          preserved; imports create new records and use each module’s duplicate
          rules.
        </p>
      </section>
    </div>
  );
}
