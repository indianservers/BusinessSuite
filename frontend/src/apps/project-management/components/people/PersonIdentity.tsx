import { assetUrl } from "@/lib/utils";
import type { Person, Context } from "./peopleTypes";
import { openPerson } from "./peopleTypes";

export function ManagePersonButton({ userId, workspaceId, projectId, label = "Manage person" }: Context & { label?: string }) {
  return <button type="button" className="rounded border px-2 py-1 text-xs hover:bg-muted" onClick={() => openPerson({ userId, workspaceId, projectId })}>{label}</button>;
}
export function PersonIdentity({ person }: { person: Partial<Person> & { email: string } }) {
  return <span className="flex min-w-0 items-center gap-3"><span className="grid h-9 w-9 shrink-0 place-items-center overflow-hidden rounded-full bg-violet-100 text-xs font-semibold text-violet-800">{person.photo_url ? <img className="h-full w-full object-cover" src={assetUrl(person.photo_url)} alt="" /> : (person.name || person.email).slice(0, 2).toUpperCase()}</span><span className="min-w-0"><strong className="block break-words text-sm">{person.name || person.email.split("@")[0]}</strong><small className="block break-all text-muted-foreground">{person.email}</small>{(person.role || person.availability) && <small className="block text-muted-foreground">{person.role?.replace(/_/g, " ")} · {person.availability || person.status}</small>}</span></span>;
}
