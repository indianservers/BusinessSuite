import type { NoteDraft, NoteRecord, NoteScope } from "@/shared/productivity/notesTypes";
export type { NoteDraft, NoteRecord, NoteScope, NoteFolder } from "@/shared/productivity/notesTypes";
export const noteBase = "/project-management/notes";
export const blankNote = (scope?: NoteScope): NoteDraft => ({title:"",content:"",project_id:scope?.project_id||null,task_id:scope?.task_id||null,folder_id:scope?.folder_id||null,tags:[],pinned:false,favorite:false,archived:false});
export const draftFrom = (note: NoteRecord): NoteDraft => ({title:note.title,content:note.content,project_id:note.project_id,task_id:note.task_id,folder_id:note.folder_id||null,tags:note.tags,pinned:note.pinned,favorite:note.favorite||false,archived:note.archived});
