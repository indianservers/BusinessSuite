import {useMobile} from "@/components/mobile/useMobile";
import "./investment-mobile.css";
import { SmartCreateSection } from "@/shared/creation/SmartCreateSection";
import GridTable from "@/shared/data-grid/GridTable";
import { NativeSelect } from "@/components/ui/native-select";
import { recordPreviewProps } from "@/components/RecordQuickPreview";
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Download, FileUp, Plus, RefreshCw, Send, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/hooks/use-toast";
import { usePageTitle } from "@/hooks/use-page-title";
import { employeeApi, taxDeclarationApi } from "@/services/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import { useAuthStore } from "@/store/authStore";

type Category = {
  id: number;
  code: string;
  name: string;
  section: string;
  maxLimit: number;
  requiresProof: boolean;
  isActive: boolean;
};

type DeclarationItem = {
  id: number;
  categoryId: number;
  categoryCode: string;
  categoryName: string;
  section: string;
  maxLimit: number;
  requiresProof: boolean;
  declaredAmount: number;
  approvedAmount: number;
  remarks?: string;
  status: string;
  proofs: Array<{ id: number; fileName: string; fileType?: string; uploadedAt?: string }>;
};

type Declaration = {
  id: number;
  employeeId: number;
  employeeName?: string;
  employeeCode?: string;
  financialYear: string;
  status: string;
  declaredTotal: number;
  approvedTotal: number;
  submittedAt?: string;
  reviewedAt?: string;
  items: DeclarationItem[];
};

const statusTone: Record<string, "secondary" | "warning" | "success" | "destructive"> = {
  draft: "secondary",
  submitted: "warning",
  approved: "success",
  partially_approved: "warning",
  rejected: "destructive",
};

function currentFinancialYear() {
  const today = new Date();
  const start = today.getMonth() >= 3 ? today.getFullYear() : today.getFullYear() - 1;
  return `${start}-${String(start + 1).slice(2)}`;
}

export default function InvestmentDeclarationPage() {
  usePageTitle("Investment Declaration");
  const phone=useMobile(480),declarationFields=useRef<HTMLDivElement>(null),reviewFields=useRef<HTMLDivElement>(null);
  const [declarationSaved,setDeclarationSaved]=useState(0),[categorySaved,setCategorySaved]=useState(0);
  const uploadLocks=useRef(new Set<string>()),downloadLocks=useRef(new Set<number>());
  const [uploadState,setUploadState]=useState<Record<string,"pending"|"error"|"done">>({});
  const [downloadState,setDownloadState]=useState<Record<number,"pending"|"error"|"done">>({});
  function validNumbers(root:HTMLDivElement|null){if(!phone)return true;for(const input of root?.querySelectorAll<HTMLInputElement>('input[type="number"]')||[]){if(!input.reportValidity())return false;}return true;}
  const qc = useQueryClient();
  const user = useAuthStore((state) => state.user);
  const hasEmployeeProfile = Boolean(user?.employee_id);
  const [financialYear, setFinancialYear] = useState(currentFinancialYear());
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [employeeId, setEmployeeId] = useState("");
  const [adminMode, setAdminMode] = useState(false);
  const [draftAmounts, setDraftAmounts] = useState<Record<number, string>>({});
  const [reviewAmounts, setReviewAmounts] = useState<Record<number, string>>({});
  const [reviewStatuses, setReviewStatuses] = useState<Record<number, string>>({});
  const [remarks, setRemarks] = useState<Record<number, string>>({});
  const [newCategory, setNewCategory] = useState({ code: "", name: "", section: "", maxLimit: "" });

  const me = useQuery({
    queryKey: ["tax-me"],
    queryFn: () => employeeApi.me().then((r) => r.data),
    retry: false,
    enabled: hasEmployeeProfile,
  });
  const employees = useQuery({ queryKey: ["tax-employees"], queryFn: () => employeeApi.list({ per_page: 100 }).then((r) => r.data.items ?? r.data) });
  const categories = useQuery({
    queryKey: ["tax-categories", financialYear],
    queryFn: () => taxDeclarationApi.categories(financialYear).then((r) => r.data as Category[]),
  });
  const employeeDeclarations = useQuery({
    queryKey: ["tax-declarations-self", me.data?.id, financialYear],
    enabled: hasEmployeeProfile && Boolean(me.data?.id) && !adminMode,
    queryFn: () => taxDeclarationApi.employeeDeclarations(me.data.id, financialYear).then((r) => r.data as Declaration[]),
  });
  const reviewDeclarations = useQuery({
    queryKey: ["tax-declarations-review", financialYear],
    enabled: adminMode,
    queryFn: () => taxDeclarationApi.list({ financialYear }).then((r) => r.data as Declaration[]),
  });

  const declarations = adminMode ? reviewDeclarations.data : employeeDeclarations.data;
  const selected = useMemo(() => declarations?.find((item) => item.id === selectedId) ?? declarations?.[0], [declarations, selectedId]);

  useEffect(() => {
    if (categories.data) {
      setDraftAmounts(Object.fromEntries(categories.data.map((category) => [category.id, ""])));
    }
  }, [categories.data]);

  useEffect(() => {
    if (selected) {
      setSelectedId(selected.id);
      setReviewAmounts(Object.fromEntries(selected.items.map((item) => [item.id, String(item.approvedAmount || item.declaredAmount || 0)])));
      setReviewStatuses(Object.fromEntries(selected.items.map((item) => [item.id, item.status === "rejected" ? "rejected" : "approved"])));
      setRemarks(Object.fromEntries(selected.items.map((item) => [item.id, item.remarks ?? ""])));
    }
  }, [selected?.id]);

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["tax-categories"] });
    qc.invalidateQueries({ queryKey: ["tax-declarations-self"] });
    qc.invalidateQueries({ queryKey: ["tax-declarations-review"] });
  };

  const createDeclaration = useMutation({
    mutationFn: () =>
      taxDeclarationApi.create({
        employeeId: adminMode && employeeId ? Number(employeeId) : undefined,
        financialYear,
        items: Object.entries(draftAmounts)
          .filter(([, amount]) => Number(amount) > 0)
          .map(([categoryId, amount]) => ({ categoryId: Number(categoryId), declaredAmount: Number(amount) })),
      }),
    onSuccess: (response) => {
      toast({ title: "Declaration saved" });
      if(phone)setDeclarationSaved(value=>value+1);
      setSelectedId(response.data.id);
      refresh();
    },
    onError: () => toast({ title: "Could not save declaration", variant: "destructive" }),
  });

  const submit = useMutation({
    mutationFn: (id: number) => taxDeclarationApi.submit(id),
    onSuccess: () => {
      toast({ title: "Declaration submitted" });
      refresh();
    },
  });

  const review = useMutation({
    mutationFn: (id: number) =>
      taxDeclarationApi.review(id, {
        items: selected?.items.map((item) => ({
          itemId: item.id,
          status: reviewStatuses[item.id] ?? "approved",
          approvedAmount: Number(reviewAmounts[item.id] ?? 0),
          remarks: remarks[item.id] || undefined,
        })),
      }),
    onSuccess: () => {
      toast({ title: "Declaration reviewed" });
      refresh();
    },
    onError: () => toast({ title: "Could not review declaration", variant: "destructive" }),
  });

  const createCategory = useMutation({
    mutationFn: () =>
      taxDeclarationApi.createCategory({
        financialYear,
        code: newCategory.code,
        name: newCategory.name,
        section: newCategory.section,
        maxLimit: Number(newCategory.maxLimit || 0),
        requiresProof: true,
      }),
    onSuccess: () => {
      toast({ title: "Category added" });
      if(phone)setCategorySaved(value=>value+1);
      setNewCategory({ code: "", name: "", section: "", maxLimit: "" });
      refresh();
    },
  });

  const uploadProof = async (declaration: Declaration, item: DeclarationItem, file?: File) => {
    if (!file) return;
    const key=`${declaration.id}:${item.id}`;
    if(phone){if(uploadLocks.current.has(key))return;uploadLocks.current.add(key);setUploadState(state=>({...state,[key]:"pending"}));}
    const formData = new FormData();
    formData.append("declarationItemId", String(item.id));
    formData.append("file", file);
    try {
      await taxDeclarationApi.uploadProof(declaration.id, formData);
      if(phone)setUploadState(state=>({...state,[key]:"done"}));
      toast({ title: "Proof uploaded" });
      refresh();
    } catch {
      if(phone)setUploadState(state=>({...state,[key]:"error"}));
      toast({ title: "Could not upload proof", variant: "destructive" });
    }finally{if(phone)uploadLocks.current.delete(key);}
  };

  const downloadProof = async (proofId: number, fileName: string) => {
    if(phone){if(downloadLocks.current.has(proofId))return;downloadLocks.current.add(proofId);setDownloadState(state=>({...state,[proofId]:"pending"}));}
    try{
      const response = await taxDeclarationApi.downloadProof(proofId);
      const url = URL.createObjectURL(response.data);
      try{const link = document.createElement("a");link.href = url;link.download = fileName;link.click();}finally{URL.revokeObjectURL(url);}
      if(phone)setDownloadState(state=>({...state,[proofId]:"done"}));
    }catch(error){if(!phone)throw error;setDownloadState(state=>({...state,[proofId]:"error"}));}
    finally{if(phone)downloadLocks.current.delete(proofId);}
  };

  return (
    <div className="hrms-investment-page space-y-5">
      <div className="flex flex-col gap-3 rounded-lg border bg-card p-5 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Indian payroll</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">Investment declaration</h1>
          <p className="mt-1 text-sm text-muted-foreground">Declare tax-saving investments, upload proofs, and review approved TDS inputs.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Input aria-label="Financial year" className="w-32" value={financialYear} onChange={(event) => setFinancialYear(event.target.value)} />
          <Button variant={adminMode ? "default" : "outline"} onClick={() => setAdminMode((value) => !value)}>
            <ShieldCheck className="h-4 w-4" /> Payroll review
          </Button>
          <Button variant="outline" onClick={refresh}>
            <RefreshCw className="h-4 w-4" /> Refresh
          </Button>
        </div>
      </div>

      {phone&&(categories.isError||(adminMode?reviewDeclarations:employeeDeclarations).isError)&&<p role="alert" className="text-sm text-destructive">Declaration information could not load. <Button variant="outline" onClick={refresh}>Retry declarations</Button></p>}
      <div className="grid gap-5 xl:grid-cols-[0.8fr_1.2fr]">
        <div className="space-y-5">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">{adminMode ? "Category setup" : "New declaration"}</CardTitle>
              <CardDescription>{adminMode ? "Configure deduction/exemption categories and limits." : "Enter declared amounts for the selected financial year."}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {adminMode && (
                <SmartCreateSection title="Create investment category" size="standard" mobileSheet={phone} completionRevision={phone?categorySaved:0}><>
                  <div className="hrms-investment-category grid gap-3 sm:grid-cols-2">
                    <Input aria-label="Category code" placeholder="Code" value={newCategory.code} onChange={(event) => setNewCategory({ ...newCategory, code: event.target.value })} />
                    <Input aria-label="Category name" placeholder="Name" value={newCategory.name} onChange={(event) => setNewCategory({ ...newCategory, name: event.target.value })} />
                    <Input aria-label="Category section" placeholder="Section" value={newCategory.section} onChange={(event) => setNewCategory({ ...newCategory, section: event.target.value })} />
                    <Input aria-label="Category maximum limit" type="number" placeholder="Max limit" value={newCategory.maxLimit} onChange={(event) => setNewCategory({ ...newCategory, maxLimit: event.target.value })} />
                  </div>
                  <Button variant="outline" onClick={() => createCategory.mutate()} disabled={!newCategory.code || !newCategory.name || (phone&&createCategory.isPending)}>
                    <Plus className="h-4 w-4" /> Add category
                  </Button>{phone&&createCategory.isError&&<p role="alert" className="text-destructive">Could not add category. Your category details are retained.</p>}
                </></SmartCreateSection>
              )}

              <SmartCreateSection title="Create investment declaration" size="large" mobileSheet={phone} completionRevision={phone?declarationSaved:0}><div ref={declarationFields} className="hrms-investment-create space-y-3">{adminMode && (
                <div className="space-y-2">
                  <Label>Create declaration for employee</Label>
                  <NativeSelect aria-label="Declaration employee" loading={employees.isFetching} error={employees.isError} value={employeeId} onChange={(event) => setEmployeeId(event.target.value)} className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                    <option value="">Select employee</option>
                    {employees.data?.map((employee: any) => (
                      <option key={employee.id} value={employee.id}>{employee.first_name} {employee.last_name}</option>
                    ))}
                  </NativeSelect>
                </div>
              )}

              <div className="space-y-2">
                {categories.data?.map((category) => (
                  <div key={category.id} className="grid gap-2 rounded-lg border p-3 sm:grid-cols-[1fr_140px] sm:items-center">
                    <div>
                      <p className="font-medium">{category.name}</p>
                      <p className="text-xs text-muted-foreground">{category.section} - {category.maxLimit ? `Limit ${formatCurrency(category.maxLimit)}` : "No fixed limit"}</p>
                    </div>
                    <Input aria-label={`Declared amount for ${category.name}`} inputMode={phone?"decimal":undefined} type="number" min="0" placeholder="Amount" value={draftAmounts[category.id] ?? ""} onChange={(event) => setDraftAmounts({ ...draftAmounts, [category.id]: event.target.value })} />
                  </div>
                ))}
              </div>
              <Button data-save-action={phone?"":undefined} onClick={() => {if(validNumbers(declarationFields.current))createDeclaration.mutate();}} disabled={createDeclaration.isPending || (!me.data?.id && !employeeId)}>
                <Plus className="h-4 w-4" /> Save declaration
              </Button>{phone&&createDeclaration.isError&&<p role="alert" className="text-destructive">Could not save declaration. Your amounts are retained.</p>}</div></SmartCreateSection>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">{adminMode ? "Submissions" : "My submissions"}</CardTitle>
              <CardDescription>{declarations?.length ?? 0} declaration(s)</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {(adminMode ? reviewDeclarations : employeeDeclarations).isLoading && <p className="rounded-lg border p-4 text-sm text-muted-foreground">Loading declarations...</p>}
              {declarations?.map((declaration) => (
                <button key={declaration.id} type="button" onClick={() => setSelectedId(declaration.id)} className={`w-full rounded-lg border p-4 text-left hover:bg-muted/40 ${selected?.id === declaration.id ? "border-primary bg-primary/5" : ""}`}>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-medium">{declaration.employeeName || "My declaration"} - {declaration.financialYear}</p>
                      <p className="text-sm text-muted-foreground">Declared {formatCurrency(declaration.declaredTotal)} - Approved {formatCurrency(declaration.approvedTotal)}</p>
                    </div>
                    <Badge variant={statusTone[declaration.status] ?? "secondary"}>{declaration.status.replace("_", " ")}</Badge>
                  </div>
                </button>
              ))}
              {!declarations?.length && (!phone||!(adminMode?reviewDeclarations:employeeDeclarations).isPending&&!(adminMode?reviewDeclarations:employeeDeclarations).isError) && <p className="rounded-lg border p-4 text-sm text-muted-foreground">No declarations yet.</p>}
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <CardTitle className="text-base">Declaration details</CardTitle>
                <CardDescription>{selected ? `${selected.employeeName || "Employee"} - ${selected.financialYear}` : "Select a declaration to review proofs and status."}</CardDescription>
              </div>
              {selected && <Badge variant={statusTone[selected.status] ?? "secondary"}>{selected.status.replace("_", " ")}</Badge>}
            </div>
          </CardHeader>
          <CardContent ref={reviewFields} className="space-y-4">
            {selected ? (
              <>
                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="rounded-lg border p-3"><p className="text-xs text-muted-foreground">Declared</p><p className="font-semibold">{formatCurrency(selected.declaredTotal)}</p></div>
                  <div className="rounded-lg border p-3"><p className="text-xs text-muted-foreground">Approved</p><p className="font-semibold">{formatCurrency(selected.approvedTotal)}</p></div>
                  <div className="rounded-lg border p-3"><p className="text-xs text-muted-foreground">Submitted</p><p className="font-semibold">{formatDate(selected.submittedAt ?? null)}</p></div>
                </div>

                <div className="overflow-x-auto rounded-lg border">
                  <GridTable gridId="apps/hrms/pages/payroll/InvestmentDeclarationPage:table-1" className="w-full min-w-[820px] text-sm">
                    <thead className="bg-muted/60 text-left">
                      <tr>
                        <th className="px-3 py-2">Category</th>
                        <th className="px-3 py-2">Declared</th>
                        <th className="px-3 py-2">Approved</th>
                        <th className="px-3 py-2">Status</th>
                        <th className="px-3 py-2">Proofs</th>
                        <th className="px-3 py-2">Remarks</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selected.items.map((item) => (
                        <tr {...recordPreviewProps(item)} key={item.id} className="border-t align-top">
                          <td className="px-3 py-2">
                            <p className="font-medium">{item.categoryName}</p>
                            <p className="text-xs text-muted-foreground">{item.section}</p>
                          </td>
                          <td className="px-3 py-2">{formatCurrency(item.declaredAmount)}</td>
                          <td className="px-3 py-2">
                            {adminMode ? (
                              <Input aria-label={`Approved amount for ${item.categoryName}`} inputMode={phone?"decimal":undefined} type="number" min="0" value={reviewAmounts[item.id] ?? ""} onChange={(event) => setReviewAmounts({ ...reviewAmounts, [item.id]: event.target.value })} />
                            ) : formatCurrency(item.approvedAmount)}
                          </td>
                          <td className="px-3 py-2">
                            {adminMode ? (
                              <NativeSelect aria-label={`Review status for ${item.categoryName}`} value={reviewStatuses[item.id] ?? "approved"} onChange={(event) => setReviewStatuses({ ...reviewStatuses, [item.id]: event.target.value })} className="h-9 rounded-md border bg-background px-2">
                                <option value="approved">Approve</option>
                                <option value="rejected">Reject</option>
                              </NativeSelect>
                            ) : <Badge variant={statusTone[item.status] ?? "secondary"}>{item.status}</Badge>}
                          </td>
                          <td className="px-3 py-2">
                            <div className="space-y-2">
                              {item.proofs.map((proof) => (
                                <Button key={proof.id} size="sm" variant="outline" disabled={phone&&downloadState[proof.id]==="pending"} onClick={() => downloadProof(proof.id, proof.fileName)}>
                                  <Download className="h-4 w-4" /> {proof.fileName}
                                </Button>
                              ))}
                              {phone&&item.proofs.some(proof=>downloadState[proof.id]==="error")&&<p role="alert" className="text-destructive">Proof download failed. Tap the file to retry.</p>}
                              {phone&&uploadState[`${selected.id}:${item.id}`]==="error"&&<p role="alert" className="text-destructive">Proof upload failed. Choose the file again to retry.</p>}
                              {!adminMode && (
                                <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-xs hover:bg-muted">
                                  <FileUp className="h-4 w-4" /> {phone&&uploadState[`${selected.id}:${item.id}`]==="pending"?"Uploading proof…":"Upload proof"}
                                  <input aria-label={phone?`Upload proof for ${item.categoryName}`:undefined} className={phone?"sr-only":"hidden"} disabled={phone&&uploadState[`${selected.id}:${item.id}`]==="pending"} type="file" accept="application/pdf,image/*" onChange={(event) => {void uploadProof(selected, item, event.target.files?.[0]);if(phone)event.currentTarget.value="";}} />
                                </label>
                              )}
                            </div>
                          </td>
                          <td className="px-3 py-2">
                            {adminMode ? <Input aria-label={`Review remarks for ${item.categoryName}`} value={remarks[item.id] ?? ""} onChange={(event) => setRemarks({ ...remarks, [item.id]: event.target.value })} /> : item.remarks || "-"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </GridTable>
                </div>

                {phone&&submit.isError&&<p role="alert" className="text-destructive">Could not submit declaration. Your declaration is retained; try again.</p>}
                {phone&&review.isError&&<p role="alert" className="text-destructive">Could not review declaration. Your review is retained.</p>}
                <div className="flex flex-wrap gap-2">
                  {!adminMode && ["draft", "rejected"].includes(selected.status) && (
                    <Button onClick={() => submit.mutate(selected.id)} disabled={submit.isPending}>
                      <Send className="h-4 w-4" /> Submit declaration
                    </Button>
                  )}
                  {adminMode && selected.status !== "draft" && (
                    <Button onClick={() => {if(validNumbers(reviewFields.current))review.mutate(selected.id);}} disabled={review.isPending}>
                      <CheckCircle2 className="h-4 w-4" /> Save review
                    </Button>
                  )}
                </div>
              </>
            ) : (
              <p className="rounded-lg border p-4 text-sm text-muted-foreground">No declaration selected.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
