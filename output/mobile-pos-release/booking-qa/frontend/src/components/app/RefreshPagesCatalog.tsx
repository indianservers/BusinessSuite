import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ListChecks } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { refreshPages } from "@/lib/refresh-pages";
import { canAccessRoute } from "@/lib/roles";
import { useAuthStore } from "@/store/authStore";

export default function RefreshPagesCatalog() {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const user = useAuthStore(state => state.user);
  const pages = useMemo(() => refreshPages.filter(page =>
    canAccessRoute(page.path, user?.role, user?.is_superuser) &&
    `${page.module} ${page.title} ${page.path}`.toLowerCase().includes(search.toLowerCase())
  ), [user?.role, user?.is_superuser, search]);
  const modules = [...new Set(pages.map(page => page.module))];
  return <Dialog open={open} onOpenChange={setOpen}>
    <Button type="button" variant="ghost" size="icon" className="shrink-0" aria-label="Pages with refresh" title="Pages with refresh" onClick={() => setOpen(true)}><ListChecks className="h-4 w-4" aria-hidden="true"/></Button>
    <DialogContent className="flex max-h-[85dvh] max-w-3xl flex-col">
      <DialogHeader><DialogTitle>Pages with refresh</DialogTitle><p className="mt-2 text-sm font-normal text-muted-foreground">Refresh reloads visible data while keeping the page open. Creation and editing screens are excluded. Selected-record routes apply when you open a record.</p></DialogHeader>
      <Input aria-label="Search refreshable pages" placeholder="Search pages or modules…" value={search} onChange={event => setSearch(event.target.value)}/>
      <p className="text-sm text-muted-foreground">{pages.length} pages available to your role</p>
      <div className="min-h-0 overflow-y-auto pr-2">
        {modules.map(module => <section key={module} className="mb-5"><h3 className="sticky top-0 border-b bg-background py-2 font-semibold">{module} <span className="text-xs font-normal text-muted-foreground">({pages.filter(page => page.module === module).length})</span></h3>
          <ul className="divide-y">{pages.filter(page => page.module === module).map(page => <li key={page.path} className="py-2 text-sm">
            {page.path.includes(":") ? <span>{page.title}</span> : <Link className="font-medium text-primary hover:underline" to={page.path} onClick={() => setOpen(false)}>{page.title}</Link>}
            <span className="block break-all text-xs text-muted-foreground">{page.path}</span>
          </li>)}</ul></section>)}
        {!pages.length && <p className="py-8 text-center text-muted-foreground">No matching pages.</p>}
      </div>
    </DialogContent>
  </Dialog>;
}
