import type { NoteRecord, NoteScope } from "./notesTypes";

export function scopeContainsNote(scope:NoteScope,note:NoteRecord):boolean {
  if(note.deleted_at)return scope.kind==="trash";
  if(scope.kind==="trash")return false;
  if(note.archived)return scope.kind==="archive";
  if(scope.kind==="archive")return false;
  if(note.can_edit===false)return scope.kind==="shared";
  if(scope.kind==="shared")return false;
  if(scope.kind==="folder")return scope.folder_id===note.folder_id;
  if(scope.kind==="task")return scope.task_id===note.task_id&&scope.project_id===note.project_id;
  if(scope.kind==="project")return scope.project_id===note.project_id;
  if(scope.kind==="personal")return note.project_id===null;
  if(scope.kind==="quick")return note.project_id===null&&note.folder_id===null;
  if(scope.kind==="favorites")return note.favorite;
  return true;
}

export type NotesPreferences = {
  viewMode: "cards" | "list" | "compact";
  width: "narrow" | "standard" | "wide";
  sort: "modified" | "created" | "title";
  explorerOpen: boolean;
  listOpen: boolean;
  scope?: NoteScope;
  noteId?: number;
};
export const notesPreferencesKey = (userId?: number) => `pms-notes-preferences:${userId || "anonymous"}`;
export function readNotesPreferences(userId?: number): NotesPreferences {
  const defaults: NotesPreferences = {viewMode:"cards",width:"standard",sort:"modified",explorerOpen:true,listOpen:true};
  if(!userId)return defaults;
  try {
    const stored=JSON.parse(localStorage.getItem(notesPreferencesKey(userId))||"null");
    if(!stored||typeof stored!=="object")return defaults;
    const scope=stored.scope;
    const kinds=["all","quick","personal","project","task","folder","shared","favorites","recent","archive","trash"];
    const safeScope=scope&&kinds.includes(scope.kind)&&typeof scope.title==="string"&&scope.title.length<=180&&["project_id","task_id","folder_id"].every(key=>scope[key]==null||(Number.isSafeInteger(scope[key])&&scope[key]>0));
    return {
      viewMode:["cards","list","compact"].includes(stored.viewMode)?stored.viewMode:defaults.viewMode,
      width:["narrow","standard","wide"].includes(stored.width)?stored.width:defaults.width,
      sort:["modified","created","title"].includes(stored.sort)?stored.sort:defaults.sort,
      explorerOpen:typeof stored.explorerOpen==="boolean"?stored.explorerOpen:true,
      listOpen:typeof stored.listOpen==="boolean"?stored.listOpen:true,
      scope:safeScope?scope:undefined,
      noteId:Number.isSafeInteger(stored.noteId)&&stored.noteId>0?stored.noteId:undefined,
    };
  } catch{return defaults;}
}
