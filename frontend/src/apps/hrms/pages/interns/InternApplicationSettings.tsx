import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, X } from "lucide-react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "@/hooks/use-toast";

export default function InternApplicationSettings() {
  const client = useQueryClient();
  const [draft, setDraft] = useState<string[] | null>(null);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const { data, isLoading, isError } = useQuery<{roles:string[];version:number}>({
    queryKey:["intern-application-settings"], queryFn:()=>api.get("/interns-hub/admin/application-settings").then(r=>r.data),
  });
  const roles = draft ?? data?.roles ?? [];
  const save = useMutation({
    mutationFn:()=>api.put("/interns-hub/admin/application-settings",{roles,version:data?.version}),
    onSuccess: async () => { await client.invalidateQueries({queryKey:["intern-application-settings"]}); setDraft(null); setError(""); toast({title:"Application roles updated",description:"New applicants will see the saved roles in Interns Hub."}); },
    onError:(e:any)=>setError(typeof e.response?.data?.detail === "string" ? e.response.data.detail : "Could not save roles. Please check the role names."),
  });
  const add = () => {
    const value=name.trim();
    if (!value || roles.some(role=>role.toLowerCase()===value.toLowerCase())) {setError("Enter a new, unique role name.");return;}
    setDraft([...roles,value]);setName("");setError("");
  };
  return <Card>
    <CardHeader><CardTitle className="text-lg">Internship roles for applications</CardTitle><p className="text-sm text-muted-foreground">Manage the roles applicants can choose in Interns Hub. Removing a role keeps existing applications unchanged.</p></CardHeader>
    <CardContent className="space-y-4">
      {isLoading ? <p>Loading application roles…</p> : isError ? <p role="alert">Application role settings could not be loaded.</p> : <>
        <div className="flex flex-wrap gap-2">{roles.map((role,index)=><span key={role} className="inline-flex items-center gap-2 rounded-lg border bg-muted/40 px-3 py-2 text-sm">{role}<button type="button" aria-label={`Remove ${role}`} disabled={save.isPending} onClick={()=>setDraft(roles.filter((_,i)=>i!==index))}><X className="h-4 w-4"/></button></span>)}</div>
        {!roles.length && <p className="text-sm text-muted-foreground">No roles are open for new applications.</p>}
        <form className="flex max-w-xl gap-2" onSubmit={e=>{e.preventDefault();add();}}>
          <Input aria-label="New internship role" placeholder="e.g. Cybersecurity Intern" value={name} maxLength={150} onChange={e=>setName(e.target.value)} disabled={save.isPending}/>
          <Button type="submit" variant="outline" disabled={!name.trim()||roles.length>=100||save.isPending}><Plus className="mr-1 h-4 w-4"/>Add role</Button>
        </form>
        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
        <div className="flex gap-2"><Button disabled={draft===null||save.isPending} onClick={()=>save.mutate()}>{save.isPending?"Saving…":"Save roles"}</Button>{draft!==null && <Button variant="ghost" disabled={save.isPending} onClick={()=>{setDraft(null);setError("");}}>Cancel changes</Button>}</div>
      </>}
    </CardContent>
  </Card>;
}
