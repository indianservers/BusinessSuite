import { FormEvent, useCallback, useEffect, useMemo, useState, type DragEvent, type KeyboardEvent, type ReactNode } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Bold,
  CalendarDays,
  CheckSquare,
  Code2,
  Clock,
  Download,
  Edit3,
  Eye,
  File as FileIcon,
  FileArchive,
  FileText,
  GitBranch,
  GripVertical,
  Heading,
  Image as ImageIcon,
  Italic,
  Link2,
  List,
  MessageSquare,
  Paperclip,
  Plus,
  Save,
  Timer,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import AskAiButton from "@/components/ai-agents/AskAiButton";
import { cn, formatDate, formatDateTime, statusColor } from "@/lib/utils";
import { commentsAPI, filesAPI, planningAPI, projectsAPI, tagsAPI, tasksAPI, timeLogsAPI, sprintsAPI, pmsUsersAPI } from "../services/api";
import { usePMSRealtime } from "../realtime";
import type {
  PMSActivity,
  PMSChecklistItem,
  PMSComment,
  PMSDevLink,
  PMSEpic,
  PMSFileAsset,
  PMSProject,
  PMSSprint,
  PMSTag,
  PMSTask,
  PMSTaskDependency,
  PMSTimeLog,
  PMSMentionUser,
  TaskPriority,
  TaskStatus,
} from "../types";

type TabKey = "comments" | "activity" | "time" | "files" | "links" | "development" | "history";
type ActivityFilter = "all" | "comments" | "changes" | "time" | "files";
type ActivitySort = "desc" | "asc";

const taskStatuses: TaskStatus[] = ["Backlog", "To Do", "In Progress", "In Review", "Blocked", "Done", "Cancelled"];
const priorities: TaskPriority[] = ["Low", "Medium", "High", "Urgent"];
const checklistCloseGuardConfig = {
  warnOnIncompleteBeforeClose: false,
};
const tabs: { key: TabKey; label: string; icon: ReactNode }[] = [
  { key: "comments", label: "Comments", icon: <MessageSquare className="h-4 w-4" /> },
  { key: "activity", label: "Activity", icon: <GitBranch className="h-4 w-4" /> },
  { key: "time", label: "Time Logs", icon: <Timer className="h-4 w-4" /> },
  { key: "files", label: "Files", icon: <Paperclip className="h-4 w-4" /> },
  { key: "links", label: "Linked Tasks", icon: <Link2 className="h-4 w-4" /> },
  { key: "development", label: "Development", icon: <Code2 className="h-4 w-4" /> },
  { key: "history", label: "History", icon: <Clock className="h-4 w-4" /> },
];

function shouldPreventClosingTask(nextStatus: string, checklist: PMSChecklistItem[]) {
  if (!checklistCloseGuardConfig.warnOnIncompleteBeforeClose) return false;
  return nextStatus === "Done" && checklist.some((item) => !item.is_completed);
}

export default function TaskDetail() {
  const { projectId, taskId } = useParams<{ projectId: string; taskId: string }>();
  const navigate = useNavigate();
  const [task, setTask] = useState<PMSTask | null>(null);
  const [project, setProject] = useState<PMSProject | null>(null);
  const [sprints, setSprints] = useState<PMSSprint[]>([]);
  const [epics, setEpics] = useState<PMSEpic[]>([]);
  const [comments, setComments] = useState<PMSComment[]>([]);
  const [activity, setActivity] = useState<PMSActivity[]>([]);
  const [files, setFiles] = useState<PMSFileAsset[]>([]);
  const [timeLogs, setTimeLogs] = useState<PMSTimeLog[]>([]);
  const [checklist, setChecklist] = useState<PMSChecklistItem[]>([]);
  const [subtasks, setSubtasks] = useState<PMSTask[]>([]);
  const [links, setLinks] = useState<PMSTaskDependency[]>([]);
  const [devLinks, setDevLinks] = useState<PMSDevLink[]>([]);
  const [tags, setTags] = useState<PMSTag[]>([]);
  const [availableTags, setAvailableTags] = useState<PMSTag[]>([]);
  const [activeTab, setActiveTab] = useState<TabKey>("comments");
  const [activityFilter, setActivityFilter] = useState<ActivityFilter>("all");
  const [activitySort, setActivitySort] = useState<ActivitySort>("desc");
  const [comment, setComment] = useState("");
  const [commentMentions, setCommentMentions] = useState<PMSMentionUser[]>([]);
  const [descriptionPreview, setDescriptionPreview] = useState(false);
  const [newChecklistItem, setNewChecklistItem] = useState("");
  const [editingChecklistId, setEditingChecklistId] = useState<number | null>(null);
  const [editingChecklistText, setEditingChecklistText] = useState("");
  const [draggedChecklistId, setDraggedChecklistId] = useState<number | null>(null);
  const [checklistError, setChecklistError] = useState<string | null>(null);
  const [newTag, setNewTag] = useState("");
  const [newSubtask, setNewSubtask] = useState("");
  const [newSubtaskPriority, setNewSubtaskPriority] = useState<TaskPriority>("Medium");
  const [newSubtaskDueDate, setNewSubtaskDueDate] = useState("");
  const [newSubtaskStoryPoints, setNewSubtaskStoryPoints] = useState("");
  const [editingSubtaskId, setEditingSubtaskId] = useState<number | null>(null);
  const [editingSubtask, setEditingSubtask] = useState<Partial<PMSTask>>({});
  const [subtaskError, setSubtaskError] = useState<string | null>(null);
  const [attachmentUploading, setAttachmentUploading] = useState(false);
  const [attachmentDragActive, setAttachmentDragActive] = useState(false);
  const [attachmentError, setAttachmentError] = useState<string | null>(null);
  const [newDependencyId, setNewDependencyId] = useState("");
  const [dependencyError, setDependencyError] = useState<string | null>(null);
  const [timeDate, setTimeDate] = useState(new Date().toISOString().slice(0, 10));
  const [timeStart, setTimeStart] = useState("");
  const [timeEnd, setTimeEnd] = useState("");
  const [timeMinutes, setTimeMinutes] = useState("30");
  const [timeDescription, setTimeDescription] = useState("");
  const [timeBillable, setTimeBillable] = useState(false);
  const [editingTimeLogId, setEditingTimeLogId] = useState<number | null>(null);
  const [timeLogError, setTimeLogError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const numericTaskId = Number(taskId);
  const effectiveProjectId = task?.project_id || Number(projectId);
  const hasProjectRoute = Boolean(projectId);

  const loadTaskData = useCallback((active = true) => {
    if (!numericTaskId) return;
    setLoading(true);
    setError(null);
    tasksAPI
      .get(numericTaskId)
      .then(async (taskResponse) => {
        if (!active) return;
        setTask(taskResponse);
        const [
          projectResponse,
          sprintResponse,
          epicResponse,
          commentResponse,
          activityResponse,
          fileResponse,
          timeResponse,
          checklistResponse,
          subtaskResponse,
          linkResponse,
          devLinkResponse,
          tagResponse,
          availableTagResponse,
        ] = await Promise.all([
          projectsAPI.get(taskResponse.project_id).catch(() => null),
          sprintsAPI.list(taskResponse.project_id).catch(() => []),
          planningAPI.listEpics(taskResponse.project_id).catch(() => []),
          commentsAPI.listForTask(taskResponse.id).catch(() => []),
          tasksAPI.listActivity(taskResponse.id).catch(() => []),
          tasksAPI.listAttachments(taskResponse.id).catch(() => []),
          tasksAPI.listTimeLogs(taskResponse.id).catch(() => []),
          tasksAPI.listChecklists(taskResponse.id).catch(() => []),
          tasksAPI.listSubtasks(taskResponse.id).catch(() => []),
          tasksAPI.listLinks(taskResponse.id).catch(() => []),
          tasksAPI.listDevLinks(taskResponse.id).catch(() => []),
          tasksAPI.listTags(taskResponse.id).catch(() => []),
          tagsAPI.list().catch(() => []),
        ]);
        if (!active) return;
        setProject(projectResponse);
        setSprints(sprintResponse);
        setEpics(epicResponse);
        setComments(commentResponse);
        setActivity(activityResponse);
        setFiles(fileResponse);
        setTimeLogs(timeResponse);
        setChecklist(checklistResponse);
        setSubtasks(subtaskResponse);
        setLinks(linkResponse);
        setDevLinks(devLinkResponse);
        setTags(tagResponse);
        setAvailableTags(availableTagResponse);
      })
      .catch((err) => {
        if (active) setError(err?.response?.data?.detail || "Unable to load task.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
  }, [numericTaskId]);

  useEffect(() => {
    let active = true;
    loadTaskData(active);
    return () => {
      active = false;
    };
  }, [loadTaskData]);

  usePMSRealtime({
    projectId: effectiveProjectId || undefined,
    taskId: numericTaskId || undefined,
    onEvent: (event) => {
      if (
        event.taskId === numericTaskId ||
        event.type === "task.comment_added" ||
        event.type === "task.attachment_added" ||
        event.type === "task.updated" ||
        event.type === "task.status_changed" ||
        event.type === "task.assignee_changed"
      ) {
        loadTaskData(true);
      }
    },
    onFallbackPoll: () => loadTaskData(true),
    showToast: false,
  });

  const selectedSprint = useMemo(() => sprints.find((item) => item.id === task?.sprint_id), [sprints, task?.sprint_id]);
  const selectedEpic = useMemo(() => epics.find((item) => item.id === task?.epic_id), [epics, task?.epic_id]);
  const checklistDone = checklist.filter((item) => item.is_completed).length;
  const checklistProgress = checklist.length ? Math.round((checklistDone / checklist.length) * 100) : 0;
  const totalLoggedMinutes = timeLogs.reduce((total, item) => total + Number(item.duration_minutes || 0), 0);
  const billableMinutes = timeLogs.filter((item) => item.is_billable).reduce((total, item) => total + Number(item.duration_minutes || 0), 0);
  const nonBillableMinutes = totalLoggedMinutes - billableMinutes;
  const completedSubtasks = subtasks.filter((item) => item.status === "Done").length;
  const subtaskProgress = subtasks.length ? Math.round((completedSubtasks / subtasks.length) * 100) : 0;
  const canNavigateBoard = hasProjectRoute && Boolean(effectiveProjectId);

  if (loading) return <div className="skeleton h-96 rounded-lg" />;
  if (error) return <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>;
  if (!task) return <div className="rounded-lg border p-8 text-center text-muted-foreground">Task not found.</div>;

  const refreshActivity = () => tasksAPI.listActivity(task.id).then(setActivity).catch(() => undefined);

  const updateTask = async (data: Partial<PMSTask>) => {
    setSaving(true);
    try {
      const updated = await tasksAPI.update(task.id, data as any);
      setTask(updated);
      refreshActivity();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Unable to save task.");
    } finally {
      setSaving(false);
    }
  };

  const addComment = async (event: FormEvent) => {
    event.preventDefault();
    if (!comment.trim()) return;
    const created = await commentsAPI.addToTask(task.id, {
      body: comment.trim(),
      body_format: "markdown",
      is_internal: true,
      mentioned_user_ids: commentMentions.map((user) => user.id),
    });
    setComments((items) => [created, ...items]);
    setComment("");
    setCommentMentions([]);
    refreshActivity();
  };

  const addChecklistItem = async (event: FormEvent) => {
    event.preventDefault();
    if (!newChecklistItem.trim()) return;
    setChecklistError(null);
    const title = newChecklistItem.trim();
    const tempItem: PMSChecklistItem = {
      id: -Date.now(),
      task_id: task.id,
      title,
      is_completed: false,
      position: checklist.length,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    setChecklist((items) => [...items, tempItem]);
    setNewChecklistItem("");
    try {
      const item = await tasksAPI.addChecklistItem(task.id, { title, is_completed: false, position: tempItem.position });
      setChecklist((items) => items.map((current) => current.id === tempItem.id ? item : current));
      refreshActivity();
    } catch (err: any) {
      setChecklist((items) => items.filter((current) => current.id !== tempItem.id));
      setChecklistError(err?.response?.data?.detail || "Unable to add checklist item.");
    }
  };

  const toggleChecklistItem = async (item: PMSChecklistItem) => {
    setChecklistError(null);
    const previous = checklist;
    const nextCompleted = !item.is_completed;
    setChecklist((items) => items.map((current) => current.id === item.id ? { ...current, is_completed: nextCompleted } : current));
    try {
      const updated = await tasksAPI.updateChecklistItem(item.id, { is_completed: nextCompleted });
      setChecklist((items) => items.map((current) => current.id === item.id ? updated : current));
      refreshActivity();
    } catch (err: any) {
      setChecklist(previous);
      setChecklistError(err?.response?.data?.detail || "Unable to update checklist item.");
    }
  };

  const startEditingChecklistItem = (item: PMSChecklistItem) => {
    setEditingChecklistId(item.id);
    setEditingChecklistText(item.title);
  };

  const saveChecklistText = async (item: PMSChecklistItem) => {
    const title = editingChecklistText.trim();
    setEditingChecklistId(null);
    if (!title || title === item.title) return;
    setChecklistError(null);
    const previous = checklist;
    setChecklist((items) => items.map((current) => current.id === item.id ? { ...current, title } : current));
    try {
      const updated = await tasksAPI.updateChecklistItem(item.id, { title });
      setChecklist((items) => items.map((current) => current.id === item.id ? updated : current));
      refreshActivity();
    } catch (err: any) {
      setChecklist(previous);
      setChecklistError(err?.response?.data?.detail || "Unable to rename checklist item.");
    }
  };

  const handleChecklistKeyDown = (event: KeyboardEvent<HTMLInputElement>, item: PMSChecklistItem) => {
    if (event.key === "Enter") {
      event.currentTarget.blur();
    }
    if (event.key === "Escape") {
      setEditingChecklistId(null);
      setEditingChecklistText(item.title);
    }
  };

  const deleteChecklistItem = async (item: PMSChecklistItem) => {
    setChecklistError(null);
    const previous = checklist;
    setChecklist((items) => items.filter((current) => current.id !== item.id));
    try {
      await tasksAPI.deleteChecklistItem(item.id);
      refreshActivity();
    } catch (err: any) {
      setChecklist(previous);
      setChecklistError(err?.response?.data?.detail || "Unable to delete checklist item.");
    }
  };

  const reorderChecklist = async (targetItemId: number) => {
    if (!draggedChecklistId || draggedChecklistId === targetItemId) return;
    setChecklistError(null);
    const previous = checklist;
    const fromIndex = checklist.findIndex((item) => item.id === draggedChecklistId);
    const toIndex = checklist.findIndex((item) => item.id === targetItemId);
    if (fromIndex < 0 || toIndex < 0) return;
    const reordered = [...checklist];
    const [moved] = reordered.splice(fromIndex, 1);
    reordered.splice(toIndex, 0, moved);
    const withPositions = reordered.map((item, index) => ({ ...item, position: index }));
    setChecklist(withPositions);
    setDraggedChecklistId(null);
    try {
      const saved = await tasksAPI.reorderChecklist(task.id, withPositions.map((item) => item.id));
      setChecklist(saved);
      refreshActivity();
    } catch (err: any) {
      setChecklist(previous);
      setChecklistError(err?.response?.data?.detail || "Unable to reorder checklist.");
    }
  };

  const handleChecklistDragOver = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
  };

  const addTag = async (event: FormEvent) => {
    event.preventDefault();
    if (!newTag.trim()) return;
    const created = await tagsAPI.create({ name: newTag.trim() });
    setAvailableTags((items) => items.some((item) => item.id === created.id) ? items : [...items, created].sort((a, b) => a.name.localeCompare(b.name)));
    const tag = await tasksAPI.addTagById(task.id, created.id);
    setTags((items) => items.some((item) => item.id === tag.id) ? items : [...items, tag].sort((a, b) => a.name.localeCompare(b.name)));
    setNewTag("");
    refreshActivity();
  };

  const attachExistingTag = async (tagId: number) => {
    if (!tagId || tags.some((tag) => tag.id === tagId)) return;
    const tag = await tasksAPI.addTagById(task.id, tagId);
    setTags((items) => items.some((item) => item.id === tag.id) ? items : [...items, tag].sort((a, b) => a.name.localeCompare(b.name)));
    refreshActivity();
  };

  const removeTag = async (tag: PMSTag) => {
    const previous = tags;
    setTags((items) => items.filter((item) => item.id !== tag.id));
    try {
      await tasksAPI.removeTag(task.id, tag.id);
      refreshActivity();
    } catch (err: any) {
      setTags(previous);
      setError(err?.response?.data?.detail || "Unable to remove tag.");
    }
  };

  const saveStoryPoints = () => {
    const points = task.story_points ?? 0;
    if (!Number.isInteger(points) || points < 0) {
      setError("Story points must be a non-negative whole number.");
      setTask({ ...task, story_points: Math.max(0, Math.floor(points || 0)) });
      return;
    }
    updateTask({ story_points: points } as any);
  };

  const uploadAttachments = async (selectedFiles: FileList | File[]) => {
    const uploads = Array.from(selectedFiles);
    if (!uploads.length) return;
    setAttachmentError(null);
    setAttachmentUploading(true);
    try {
      const created = await Promise.all(uploads.map((file) => filesAPI.uploadToTask(task.id, file)));
      setFiles((items) => [...created, ...items]);
      refreshActivity();
    } catch (err: any) {
      setAttachmentError(err?.response?.data?.detail || "Unable to upload attachment.");
    } finally {
      setAttachmentUploading(false);
      setAttachmentDragActive(false);
    }
  };

  const deleteAttachment = async (file: PMSFileAsset) => {
    const previous = files;
    setFiles((items) => items.filter((item) => item.id !== file.id));
    try {
      await filesAPI.deleteAttachment(file.id);
      refreshActivity();
    } catch (err: any) {
      setFiles(previous);
      setAttachmentError(err?.response?.data?.detail || "Unable to delete attachment.");
    }
  };

  const logTime = async (event: FormEvent) => {
    event.preventDefault();
    const minutes = Number(timeMinutes);
    if (!minutes || minutes <= 0) {
      setTimeLogError("Duration must be greater than zero.");
      return;
    }
    setTimeLogError(null);
    const payload = {
      project_id: task.project_id,
      task_id: task.id,
      log_date: timeDate,
      start_time: timeStart ? `${timeDate}T${timeStart}:00` : undefined,
      end_time: timeEnd ? `${timeDate}T${timeEnd}:00` : undefined,
      duration_minutes: minutes,
      description: timeDescription.trim() || undefined,
      is_billable: timeBillable,
    };
    try {
      if (editingTimeLogId) {
        const updated = await timeLogsAPI.update(editingTimeLogId, payload);
        setTimeLogs((items) => items.map((item) => item.id === updated.id ? updated : item));
      } else {
        const created = await tasksAPI.addTimeLog(task.id, payload);
        setTimeLogs((items) => [created, ...items]);
      }
      setEditingTimeLogId(null);
      setTimeStart("");
      setTimeEnd("");
      setTimeBillable(false);
      setTimeDescription("");
      setTimeMinutes("30");
      refreshActivity();
    } catch (err: any) {
      setTimeLogError(err?.response?.data?.detail || "Unable to save time log.");
    }
  };

  const editTimeLog = (log: PMSTimeLog) => {
    setEditingTimeLogId(log.id);
    setTimeDate(log.log_date);
    setTimeStart(log.start_time ? log.start_time.slice(11, 16) : "");
    setTimeEnd(log.end_time ? log.end_time.slice(11, 16) : "");
    setTimeMinutes(String(log.duration_minutes));
    setTimeDescription(log.description || "");
    setTimeBillable(log.is_billable);
    setTimeLogError(null);
    setActiveTab("time");
  };

  const cancelTimeLogEdit = () => {
    setEditingTimeLogId(null);
    setTimeDate(new Date().toISOString().slice(0, 10));
    setTimeStart("");
    setTimeEnd("");
    setTimeMinutes("30");
    setTimeDescription("");
    setTimeBillable(false);
    setTimeLogError(null);
  };

  const deleteTimeLog = async (log: PMSTimeLog) => {
    const previous = timeLogs;
    setTimeLogs((items) => items.filter((item) => item.id !== log.id));
    try {
      await timeLogsAPI.delete(log.id);
      refreshActivity();
    } catch (err: any) {
      setTimeLogs(previous);
      setTimeLogError(err?.response?.data?.detail || "Unable to delete time log.");
    }
  };

  const addSubtask = async (event: FormEvent) => {
    event.preventDefault();
    if (!newSubtask.trim()) return;
    setSubtaskError(null);
    const points = newSubtaskStoryPoints === "" ? undefined : Number(newSubtaskStoryPoints);
    if (points !== undefined && (!Number.isInteger(points) || points < 0)) {
      setSubtaskError("Story points must be a non-negative whole number.");
      return;
    }
    try {
      const created = await tasksAPI.createSubtask(task.id, {
        title: newSubtask.trim(),
        description: "",
        status: "To Do",
        priority: newSubtaskPriority,
        assignee_user_id: task.assignee_user_id,
        due_date: newSubtaskDueDate || undefined,
        story_points: points,
      });
      setSubtasks((items) => [...items, created]);
      setTask((current) => current ? { ...current, subtask_count: (current.subtask_count || 0) + 1 } : current);
      setNewSubtask("");
      setNewSubtaskDueDate("");
      setNewSubtaskStoryPoints("");
      setNewSubtaskPriority("Medium");
      refreshActivity();
    } catch (err: any) {
      setSubtaskError(err?.response?.data?.detail || "Unable to add sub-task.");
    }
  };

  const startEditingSubtask = (item: PMSTask) => {
    setEditingSubtaskId(item.id);
    setEditingSubtask({
      title: item.title,
      description: item.description || "",
      status: item.status,
      priority: item.priority,
      assignee_user_id: item.assignee_user_id,
      due_date: item.due_date,
      story_points: item.story_points,
    });
    setSubtaskError(null);
  };

  const saveSubtask = async (item: PMSTask) => {
    setSubtaskError(null);
    const points = editingSubtask.story_points;
    if (points !== undefined && points !== null && (!Number.isInteger(Number(points)) || Number(points) < 0)) {
      setSubtaskError("Story points must be a non-negative whole number.");
      return;
    }
    try {
      const updated = await tasksAPI.update(item.id, editingSubtask as any);
      setSubtasks((items) => items.map((current) => current.id === updated.id ? updated : current));
      setEditingSubtaskId(null);
      setEditingSubtask({});
      refreshActivity();
    } catch (err: any) {
      setSubtaskError(err?.response?.data?.detail || "Unable to update sub-task.");
    }
  };

  const completeSubtask = async (item: PMSTask) => {
    setSubtaskError(null);
    const nextStatus = item.status === "Done" ? "To Do" : "Done";
    const previous = subtasks;
    setSubtasks((items) => items.map((current) => current.id === item.id ? { ...current, status: nextStatus as TaskStatus } : current));
    try {
      const updated = await tasksAPI.updateStatus(item.id, nextStatus);
      setSubtasks((items) => items.map((current) => current.id === updated.id ? updated : current));
      setTask((current) => current ? {
        ...current,
        completed_subtask_count: subtasks.filter((subtask) => subtask.id === item.id ? nextStatus === "Done" : subtask.status === "Done").length,
      } : current);
      refreshActivity();
    } catch (err: any) {
      setSubtasks(previous);
      setSubtaskError(err?.response?.data?.detail || "Unable to complete sub-task.");
    }
  };

  const deleteSubtask = async (item: PMSTask) => {
    setSubtaskError(null);
    const previous = subtasks;
    setSubtasks((items) => items.filter((current) => current.id !== item.id));
    try {
      await tasksAPI.delete(item.id);
      setTask((current) => current ? {
        ...current,
        subtask_count: Math.max((current.subtask_count || 1) - 1, 0),
        completed_subtask_count: Math.max((current.completed_subtask_count || 0) - (item.status === "Done" ? 1 : 0), 0),
      } : current);
      refreshActivity();
    } catch (err: any) {
      setSubtasks(previous);
      setSubtaskError(err?.response?.data?.detail || "Unable to delete sub-task.");
    }
  };

  const addDependency = async (event: FormEvent) => {
    event.preventDefault();
    const dependsOnTaskId = Number(newDependencyId);
    if (!dependsOnTaskId || dependsOnTaskId === task.id) {
      setDependencyError("Enter a different task ID to link as a blocker.");
      return;
    }
    setDependencyError(null);
    try {
      await tasksAPI.addDependency(task.id, dependsOnTaskId);
      const updatedLinks = await tasksAPI.listLinks(task.id);
      setLinks(updatedLinks);
      setNewDependencyId("");
      refreshActivity();
    } catch (err: any) {
      setDependencyError(err?.response?.data?.detail || "Unable to link task.");
    }
  };

  return (
    <div className="space-y-6">
      <Button variant="ghost" onClick={() => navigate(canNavigateBoard ? `/pms/projects/${effectiveProjectId}/board` : "/pms/tasks")}>
        <ArrowLeft className="h-4 w-4" />{canNavigateBoard ? "Back to board" : "Back to tasks"}
      </Button>

      <Card>
        <CardContent className="p-5">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
            <div className="min-w-0 space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">{task.task_key || `Task #${task.id}`}</Badge>
                <span className="text-sm text-muted-foreground">{project?.name || `Project #${task.project_id}`}</span>
                {selectedSprint ? <Badge variant="secondary">{selectedSprint.name}</Badge> : null}
                {selectedEpic ? <Badge variant="secondary">{selectedEpic.epic_key}</Badge> : null}
              </div>
              <Input
                value={task.title}
                onChange={(event) => setTask({ ...task, title: event.target.value })}
                onBlur={() => updateTask({ title: task.title })}
                className="h-auto border-0 px-0 text-2xl font-semibold shadow-none focus-visible:ring-0"
              />
              <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
                <Badge className={statusColor(task.status)}>{task.status}</Badge>
                <Badge className={statusColor(task.priority)}>{task.priority}</Badge>
                <span className="inline-flex items-center gap-2">
                  <Avatar label={userLabel(task.assignee_user_id, "Unassigned")} />
                  {userLabel(task.assignee_user_id, "Unassigned")}
                </span>
                <span className="inline-flex items-center gap-1"><CalendarDays className="h-4 w-4" />Due {formatDate(task.due_date || null)}</span>
                <span>{task.story_points ?? 0} pts</span>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <AskAiButton
                module="PMS"
                relatedEntityType="task"
                relatedEntityId={task.id}
                defaultAgentCode="pms_deadline_risk"
                defaultPrompt="Analyze deadline risk for this task/project."
              />
              <Button onClick={() => updateTask({ title: task.title, description: task.description })} disabled={saving}>
                <Save className="h-4 w-4" />{saving ? "Saving" : "Save"}
              </Button>
              <QuickAnchor label="Comment" target="comments" setActiveTab={setActiveTab} />
              <QuickAnchor label="Attach File" target="files" setActiveTab={setActiveTab} />
              <QuickAnchor label="Log Time" target="time" setActiveTab={setActiveTab} />
              <Button variant="outline" onClick={() => document.getElementById("add-checklist-item")?.focus()}><CheckSquare className="h-4 w-4" />Add Checklist</Button>
              <Button variant="outline" onClick={() => document.getElementById("add-subtask")?.focus()}><Plus className="h-4 w-4" />Add Sub-task</Button>
            </div>
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <DetailMetric label="Checklist" value={`${checklistDone}/${checklist.length}`} hint={`${checklistProgress}% complete`} />
            <DetailMetric label="Sub-tasks" value={`${completedSubtasks}/${subtasks.length}`} hint={`${subtaskProgress}% complete`} />
            <DetailMetric label="Time logged" value={formatMinutes(totalLoggedMinutes)} hint={`${formatMinutes(billableMinutes)} billable`} />
            <DetailMetric label="Files" value={String(files.length)} hint="attachments" />
            <DetailMetric label="Links" value={String(links.length)} hint="dependencies" />
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="space-y-6">
          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2"><FileText className="h-5 w-5" />Description</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <MarkdownToolbar
                value={task.description || ""}
                onChange={(value) => setTask({ ...task, description: value })}
                preview={descriptionPreview}
                setPreview={setDescriptionPreview}
              />
              {descriptionPreview ? (
                <MarkdownView value={task.description || ""} className="min-h-52 rounded-md border bg-muted/20 p-3 text-sm" />
              ) : (
                <textarea
                value={task.description || ""}
                onChange={(event) => setTask({ ...task, description: event.target.value })}
                onBlur={() => updateTask({ description: task.description })}
                placeholder="Add requirements, acceptance criteria, context, links, or implementation notes. Markdown is supported."
                className="min-h-52 w-full rounded-md border bg-background px-3 py-2 text-sm"
                />
              )}
              {!task.description ? <div className="rounded-md border bg-muted/40 p-3 text-sm text-muted-foreground">No description yet.</div> : null}
            </CardContent>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader><CardTitle className="flex items-center gap-2"><CheckSquare className="h-5 w-5" />Checklist</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium">{checklistDone}/{checklist.length} completed</span>
                    <span className="text-muted-foreground">{checklistProgress}%</span>
                  </div>
                  <div className="h-2 rounded-full bg-muted">
                    <div className="h-2 rounded-full bg-primary transition-all" style={{ width: `${checklistProgress}%` }} />
                  </div>
                </div>
                {checklistError ? <div className="rounded-md border border-red-200 bg-red-50 p-2 text-xs text-red-700">{checklistError}</div> : null}
                {checklist.map((item) => (
                  <div
                    key={item.id}
                    draggable={item.id > 0}
                    onDragStart={() => setDraggedChecklistId(item.id)}
                    onDragOver={handleChecklistDragOver}
                    onDrop={() => reorderChecklist(item.id)}
                    className={cn("flex items-center gap-2 rounded-md border px-2 py-2 text-sm transition hover:bg-muted/40", draggedChecklistId === item.id && "opacity-60")}
                  >
                    <GripVertical className="h-4 w-4 shrink-0 cursor-grab text-muted-foreground" />
                    <input type="checkbox" checked={item.is_completed} onChange={() => toggleChecklistItem(item)} className="shrink-0" />
                    {editingChecklistId === item.id ? (
                      <Input
                        autoFocus
                        value={editingChecklistText}
                        onChange={(event) => setEditingChecklistText(event.target.value)}
                        onBlur={() => saveChecklistText(item)}
                        onKeyDown={(event) => handleChecklistKeyDown(event, item)}
                        className="h-8"
                      />
                    ) : (
                      <button type="button" onClick={() => startEditingChecklistItem(item)} className={cn("min-w-0 flex-1 truncate text-left", item.is_completed && "line-through text-muted-foreground")}>
                        {item.title}
                      </button>
                    )}
                    <Button type="button" variant="ghost" size="icon" onClick={() => deleteChecklistItem(item)} disabled={item.id < 0} aria-label={`Delete checklist item ${item.title}`}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
                {!checklist.length ? <EmptyLine>No checklist items yet.</EmptyLine> : null}
                <form onSubmit={addChecklistItem} className="flex gap-2">
                  <Input id="add-checklist-item" value={newChecklistItem} onChange={(event) => setNewChecklistItem(event.target.value)} placeholder="Add checklist item" />
                  <Button type="submit" size="sm"><Plus className="h-4 w-4" />Add</Button>
                </form>
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle>Tags and Estimates</CardTitle></CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-wrap gap-2">
                  {tags.map((tag) => (
                    <Badge key={tag.id} variant="outline" className="gap-1">
                      {tag.name}
                      <button type="button" onClick={() => removeTag(tag)} aria-label={`Remove ${tag.name}`}>
                        <X className="h-3 w-3" />
                      </button>
                    </Badge>
                  ))}
                  {!tags.length ? <EmptyLine>No tags yet.</EmptyLine> : null}
                </div>
                <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
                  <select
                    value=""
                    onChange={(event) => attachExistingTag(Number(event.target.value))}
                    className="h-10 rounded-md border bg-background px-3 text-sm"
                  >
                    <option value="">Select existing tag</option>
                    {availableTags.filter((tag) => !tags.some((item) => item.id === tag.id)).map((tag) => <option key={tag.id} value={tag.id}>{tag.name}</option>)}
                  </select>
                </div>
                <form onSubmit={addTag} className="flex gap-2">
                  <Input value={newTag} onChange={(event) => setNewTag(event.target.value)} placeholder="Create and add tag" />
                  <Button type="submit" size="sm"><Plus className="h-4 w-4" />Add</Button>
                </form>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Story points">
                    <Input type="number" min="0" step="1" value={task.story_points ?? ""} onChange={(event) => setTask({ ...task, story_points: Number(event.target.value || 0) })} onBlur={saveStoryPoints} />
                  </Field>
                  <Field label="Estimate hours">
                    <Input type="number" value={task.estimated_hours ?? ""} onChange={(event) => setTask({ ...task, estimated_hours: Number(event.target.value || 0) })} onBlur={() => updateTask({ estimated_hours: task.estimated_hours } as any)} />
                  </Field>
                </div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader><CardTitle>Sub-tasks</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium">{completedSubtasks}/{subtasks.length} completed</span>
                  <span className="text-muted-foreground">{subtaskProgress}%</span>
                </div>
                <div className="h-2 rounded-full bg-muted">
                  <div className="h-2 rounded-full bg-primary transition-all" style={{ width: `${subtaskProgress}%` }} />
                </div>
              </div>
              {subtaskError ? <div className="rounded-md border border-red-200 bg-red-50 p-2 text-xs text-red-700">{subtaskError}</div> : null}
              <div className="space-y-2">
                {subtasks.map((item) => (
                  <SubtaskRow
                    key={item.id}
                    task={item}
                    editing={editingSubtaskId === item.id}
                    draft={editingSubtask}
                    setDraft={setEditingSubtask}
                    startEditing={startEditingSubtask}
                    cancelEditing={() => {
                      setEditingSubtaskId(null);
                      setEditingSubtask({});
                    }}
                    saveSubtask={saveSubtask}
                    completeSubtask={completeSubtask}
                    deleteSubtask={deleteSubtask}
                    openSubtask={() => navigate(`/pms/projects/${item.project_id}/tasks/${item.id}`)}
                  />
                ))}
                {!subtasks.length ? <EmptyLine>No sub-tasks yet.</EmptyLine> : null}
              </div>
              <form onSubmit={addSubtask} className="rounded-md border p-3">
                <div className="grid gap-2 md:grid-cols-[minmax(12rem,1fr)_9rem_9rem_7rem_auto]">
                  <Input id="add-subtask" value={newSubtask} onChange={(event) => setNewSubtask(event.target.value)} placeholder="Add sub-task title" />
                  <select value={newSubtaskPriority} onChange={(event) => setNewSubtaskPriority(event.target.value as TaskPriority)} className="h-10 rounded-md border bg-background px-3 text-sm">
                    {priorities.map((item) => <option key={item}>{item}</option>)}
                  </select>
                  <Input type="date" value={newSubtaskDueDate} onChange={(event) => setNewSubtaskDueDate(event.target.value)} />
                  <Input type="number" min="0" step="1" value={newSubtaskStoryPoints} onChange={(event) => setNewSubtaskStoryPoints(event.target.value)} placeholder="Pts" />
                  <Button type="submit" size="sm"><Plus className="h-4 w-4" />Add</Button>
                </div>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex flex-wrap gap-2">
                {tabs.map((tab) => (
                  <Button key={tab.key} type="button" variant={activeTab === tab.key ? "default" : "outline"} size="sm" onClick={() => setActiveTab(tab.key)}>
                    {tab.icon}{tab.label}
                  </Button>
                ))}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {activeTab === "comments" ? (
                <CommentsTab
                  taskId={task.id}
                  projectId={task.project_id}
                  comments={comments}
                  comment={comment}
                  setComment={setComment}
                  mentions={commentMentions}
                  setMentions={setCommentMentions}
                  addComment={addComment}
                />
              ) : null}
              {activeTab === "activity" ? <ActivityList items={activity} filter={activityFilter} setFilter={setActivityFilter} sort={activitySort} setSort={setActivitySort} /> : null}
              {activeTab === "history" ? <ActivityList items={activity.filter((item) => item.action.includes("updated") || item.action.includes("changed") || item.action.includes("created"))} filter={activityFilter} setFilter={setActivityFilter} sort={activitySort} setSort={setActivitySort} /> : null}
              {activeTab === "time" ? (
                <TimeTab
                  logs={timeLogs}
                  totalMinutes={totalLoggedMinutes}
                  billableMinutes={billableMinutes}
                  nonBillableMinutes={nonBillableMinutes}
                  date={timeDate}
                  setDate={setTimeDate}
                  start={timeStart}
                  setStart={setTimeStart}
                  end={timeEnd}
                  setEnd={setTimeEnd}
                  minutes={timeMinutes}
                  setMinutes={setTimeMinutes}
                  description={timeDescription}
                  setDescription={setTimeDescription}
                  billable={timeBillable}
                  setBillable={setTimeBillable}
                  editingId={editingTimeLogId}
                  error={timeLogError}
                  logTime={logTime}
                  editTimeLog={editTimeLog}
                  deleteTimeLog={deleteTimeLog}
                  cancelEdit={cancelTimeLogEdit}
                />
              ) : null}
              {activeTab === "files" ? (
                <FilesTab
                  files={files}
                  uploading={attachmentUploading}
                  dragActive={attachmentDragActive}
                  setDragActive={setAttachmentDragActive}
                  error={attachmentError}
                  uploadAttachments={uploadAttachments}
                  deleteAttachment={deleteAttachment}
                />
              ) : null}
              {activeTab === "links" ? (
                <LinksTab
                  links={links}
                  currentTaskId={task.id}
                  dependencyId={newDependencyId}
                  setDependencyId={setNewDependencyId}
                  dependencyError={dependencyError}
                  addDependency={addDependency}
                />
              ) : null}
              {activeTab === "development" ? <DevelopmentTab links={devLinks} /> : null}
            </CardContent>
          </Card>
        </div>

        <aside className="space-y-4">
          <Card>
            <CardHeader><CardTitle>People</CardTitle></CardHeader>
            <CardContent className="space-y-3 text-sm">
              <PersonRow label="Assignee" value={userLabel(task.assignee_user_id, "Unassigned")} />
              <PersonRow label="Reporter" value={userLabel(task.reporter_user_id, "No reporter")} />
              <Property label="Watchers" value="Not configured" />
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Properties</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <Field label="Status">
                <select
                  value={task.status}
                  onChange={(event) => {
                    const nextStatus = event.target.value as TaskStatus;
                    if (shouldPreventClosingTask(nextStatus, checklist)) {
                      setChecklistError("Complete all checklist items before closing this task.");
                      return;
                    }
                    updateTask({ status: nextStatus });
                  }}
                  className="h-10 w-full rounded-md border bg-background px-3 text-sm"
                >
                  {taskStatuses.map((item) => <option key={item}>{item}</option>)}
                </select>
              </Field>
              <Field label="Priority">
                <select value={task.priority} onChange={(event) => updateTask({ priority: event.target.value as TaskPriority })} className="h-10 w-full rounded-md border bg-background px-3 text-sm">
                  {priorities.map((item) => <option key={item}>{item}</option>)}
                </select>
              </Field>
              <Field label="Sprint">
                <select value={task.sprint_id || ""} onChange={(event) => updateTask({ sprint_id: event.target.value ? Number(event.target.value) : null } as any)} className="h-10 w-full rounded-md border bg-background px-3 text-sm">
                  <option value="">No sprint</option>
                  {sprints.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                </select>
              </Field>
              <Field label="Epic">
                <select value={task.epic_id || ""} onChange={(event) => updateTask({ epic_id: event.target.value ? Number(event.target.value) : null } as any)} className="h-10 w-full rounded-md border bg-background px-3 text-sm">
                  <option value="">No epic</option>
                  {epics.map((item) => <option key={item.id} value={item.id}>{item.epic_key} - {item.name}</option>)}
                </select>
              </Field>
              <Field label="Due date"><Input type="date" value={task.due_date || ""} onChange={(event) => updateTask({ due_date: event.target.value || null } as any)} /></Field>
              <Field label="Start date"><Input type="date" value={task.start_date || ""} onChange={(event) => updateTask({ start_date: event.target.value || null } as any)} /></Field>
              <Field label="Story points"><Input type="number" min="0" step="1" value={task.story_points ?? ""} onChange={(event) => setTask({ ...task, story_points: Number(event.target.value || 0) })} onBlur={saveStoryPoints} /></Field>
              <Field label="Created">{formatDateTime(task.created_at || null)}</Field>
              <Field label="Updated">{formatDateTime(task.updated_at || null)}</Field>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Custom Fields</CardTitle></CardHeader>
            <CardContent className="space-y-3 text-sm">
              <Property label="Work type" value={task.work_type} />
              <Property label="Component" value={task.component || "-"} />
              <Property label="Severity" value={task.severity || "-"} />
              <Property label="Fix version" value={task.fix_version || "-"} />
              <Property label="Security" value={task.security_level} />
              <Property label="Build" value={task.development_build} />
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}

function QuickAnchor({ label, target, setActiveTab }: { label: string; target: TabKey; setActiveTab: (tab: TabKey) => void }) {
  return <Button variant="outline" onClick={() => setActiveTab(target)}>{label}</Button>;
}

function Avatar({ label }: { label: string }) {
  const initials = label
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("") || "?";
  return <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">{initials}</span>;
}

function DetailMetric({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-md border bg-muted/30 p-3 text-sm">
      <p className="text-muted-foreground">{label}</p>
      <p className="mt-1 text-lg font-semibold">{value}</p>
      <p className="text-xs text-muted-foreground">{hint}</p>
    </div>
  );
}

function PersonRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-muted-foreground">{label}</span>
      <span className="flex min-w-0 items-center gap-2 font-medium">
        <Avatar label={value} />
        <span className="truncate">{value}</span>
      </span>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <div className="space-y-2"><Label className="text-xs uppercase text-muted-foreground">{label}</Label><div className="text-sm">{children}</div></div>;
}

function Property({ label, value }: { label: string; value: ReactNode }) {
  return <div className="flex items-center justify-between gap-3"><span className="text-muted-foreground">{label}</span><span className="text-right font-medium">{value}</span></div>;
}

function EmptyLine({ children }: { children: ReactNode }) {
  return <p className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">{children}</p>;
}

function SubtaskRow({
  task,
  editing,
  draft,
  setDraft,
  startEditing,
  cancelEditing,
  saveSubtask,
  completeSubtask,
  deleteSubtask,
  openSubtask,
}: {
  task: PMSTask;
  editing: boolean;
  draft: Partial<PMSTask>;
  setDraft: (value: Partial<PMSTask>) => void;
  startEditing: (task: PMSTask) => void;
  cancelEditing: () => void;
  saveSubtask: (task: PMSTask) => void;
  completeSubtask: (task: PMSTask) => void;
  deleteSubtask: (task: PMSTask) => void;
  openSubtask: () => void;
}) {
  if (editing) {
    return (
      <div className="rounded-md border bg-muted/20 p-3 text-sm">
        <div className="grid gap-2 lg:grid-cols-[minmax(12rem,1fr)_9rem_9rem_8rem_7rem]">
          <Input value={draft.title || ""} onChange={(event) => setDraft({ ...draft, title: event.target.value })} />
          <select value={draft.status || task.status} onChange={(event) => setDraft({ ...draft, status: event.target.value as TaskStatus })} className="h-10 rounded-md border bg-background px-3 text-sm">
            {taskStatuses.map((item) => <option key={item}>{item}</option>)}
          </select>
          <select value={draft.priority || task.priority} onChange={(event) => setDraft({ ...draft, priority: event.target.value as TaskPriority })} className="h-10 rounded-md border bg-background px-3 text-sm">
            {priorities.map((item) => <option key={item}>{item}</option>)}
          </select>
          <Input type="date" value={draft.due_date || ""} onChange={(event) => setDraft({ ...draft, due_date: event.target.value || undefined })} />
          <Input type="number" min="0" step="1" value={draft.story_points ?? ""} onChange={(event) => setDraft({ ...draft, story_points: event.target.value === "" ? undefined : Number(event.target.value) })} />
        </div>
        <textarea
          value={draft.description || ""}
          onChange={(event) => setDraft({ ...draft, description: event.target.value })}
          placeholder="Sub-task description"
          className="mt-2 min-h-20 w-full rounded-md border bg-background px-3 py-2 text-sm"
        />
        <div className="mt-2 flex flex-wrap justify-end gap-2">
          <Button type="button" size="sm" variant="outline" onClick={cancelEditing}>Cancel</Button>
          <Button type="button" size="sm" onClick={() => saveSubtask(task)}>Save</Button>
        </div>
      </div>
    );
  }
  return (
    <div className="rounded-md border px-3 py-2 text-sm">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-primary">{task.task_key}</span>
            <Badge className={statusColor(task.status)}>{task.status}</Badge>
            <Badge className={statusColor(task.priority)}>{task.priority}</Badge>
            {task.story_points !== undefined && task.story_points !== null ? <span className="text-xs text-muted-foreground">{task.story_points} pts</span> : null}
          </div>
          <button type="button" onClick={openSubtask} className="mt-1 line-clamp-2 text-left font-medium hover:text-primary">
            {task.title}
          </button>
          <p className="mt-1 text-xs text-muted-foreground">
            {userLabel(task.assignee_user_id, "Unassigned")} / Due {formatDate(task.due_date || null)}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Button type="button" size="sm" variant="outline" onClick={() => completeSubtask(task)}>
            {task.status === "Done" ? "Reopen" : "Complete"}
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={() => startEditing(task)}>Edit</Button>
          <Button type="button" size="sm" variant="ghost" onClick={openSubtask}>Open</Button>
          <Button type="button" size="sm" variant="ghost" onClick={() => deleteSubtask(task)} aria-label={`Delete ${task.title}`}>
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}

function CommentsTab({
  taskId,
  projectId,
  comments,
  comment,
  setComment,
  mentions,
  setMentions,
  addComment,
}: {
  taskId: number;
  projectId: number;
  comments: PMSComment[];
  comment: string;
  setComment: (value: string) => void;
  mentions: PMSMentionUser[];
  setMentions: (users: PMSMentionUser[]) => void;
  addComment: (event: FormEvent) => void;
}) {
  const [preview, setPreview] = useState(false);
  return (
    <>
      <form onSubmit={addComment} className="space-y-3 rounded-md border p-3">
        <MarkdownToolbar value={comment} onChange={setComment} preview={preview} setPreview={setPreview} />
        {preview ? (
          <MarkdownView value={comment} className="min-h-32 rounded-md border bg-muted/20 p-3 text-sm" />
        ) : (
          <MentionMarkdownTextarea
            taskId={taskId}
            projectId={projectId}
            value={comment}
            onChange={setComment}
            mentions={mentions}
            onMentionsChange={setMentions}
          />
        )}
        {mentions.length ? (
          <div className="flex flex-wrap gap-2">
            {mentions.map((user) => <Badge key={user.id} variant="outline">@{user.name || user.email}</Badge>)}
          </div>
        ) : <p className="text-xs text-muted-foreground">Type @ to mention a project teammate.</p>}
        <div className="flex justify-end">
          <Button type="submit">Comment</Button>
        </div>
      </form>
      {comments.map((item) => (
        <div key={item.id} className="rounded-md border p-3 text-sm">
          <MarkdownView value={item.body} />
          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span>{formatDateTime(item.created_at)}</span>
            {item.is_edited ? <Badge variant="outline">Edited</Badge> : null}
            {item.mentions?.map((mention) => mention.user ? <Badge key={mention.id} variant="outline">@{mention.user.name || mention.user.email}</Badge> : null)}
          </div>
        </div>
      ))}
      {!comments.length ? <EmptyLine>No comments yet.</EmptyLine> : null}
    </>
  );
}

function MarkdownToolbar({ value, onChange, preview, setPreview }: { value: string; onChange: (value: string) => void; preview: boolean; setPreview: (value: boolean) => void }) {
  const wrap = (before: string, after = before, placeholder = "text") => onChange(`${value}${value ? "\n" : ""}${before}${placeholder}${after}`);
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button type="button" size="sm" variant="outline" onClick={() => wrap("## ", "", "Heading")}><Heading className="h-4 w-4" />Heading</Button>
      <Button type="button" size="sm" variant="outline" onClick={() => wrap("**", "**", "bold")}><Bold className="h-4 w-4" />Bold</Button>
      <Button type="button" size="sm" variant="outline" onClick={() => wrap("_", "_", "italic")}><Italic className="h-4 w-4" />Italic</Button>
      <Button type="button" size="sm" variant="outline" onClick={() => wrap("- ", "", "List item")}><List className="h-4 w-4" />List</Button>
      <Button type="button" size="sm" variant="outline" onClick={() => wrap("```\n", "\n```", "code")}><Code2 className="h-4 w-4" />Code</Button>
      <Button type="button" size="sm" variant="outline" onClick={() => wrap("[", "](https://)", "link")}><Link2 className="h-4 w-4" />Link</Button>
      <Button type="button" size="sm" variant={preview ? "default" : "outline"} onClick={() => setPreview(!preview)}>
        {preview ? <Edit3 className="h-4 w-4" /> : <Eye className="h-4 w-4" />}{preview ? "Edit" : "Preview"}
      </Button>
    </div>
  );
}

function MentionMarkdownTextarea({
  taskId,
  projectId,
  value,
  onChange,
  mentions,
  onMentionsChange,
}: {
  taskId: number;
  projectId: number;
  value: string;
  onChange: (value: string) => void;
  mentions: PMSMentionUser[];
  onMentionsChange: (users: PMSMentionUser[]) => void;
}) {
  const [suggestions, setSuggestions] = useState<PMSMentionUser[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [token, setToken] = useState("");

  const updateValue = (next: string) => {
    onChange(next);
    const match = next.slice(0).match(/@([\w.\-+]*)$/);
    if (match) {
      const query = match[1] || "";
      setToken(query);
      setShowSuggestions(true);
      pmsUsersAPI.search({ q: query, taskId, projectId }).then(setSuggestions).catch(() => setSuggestions([]));
    } else {
      setShowSuggestions(false);
    }
  };

  const insertMention = (user: PMSMentionUser) => {
    const next = value.replace(/@([\w.\-+]*)$/, `@[${user.name || user.email}](user:${user.id}) `);
    onChange(next);
    if (!mentions.some((item) => item.id === user.id)) onMentionsChange([...mentions, user]);
    setShowSuggestions(false);
  };

  return (
    <div className="relative">
      <textarea
        value={value}
        onChange={(event) => updateValue(event.target.value)}
        placeholder="Write a markdown comment. Use @ to mention a teammate."
        className="min-h-32 w-full rounded-md border bg-background px-3 py-2 text-sm"
      />
      {showSuggestions ? (
        <div className="absolute left-2 top-12 z-20 w-72 rounded-md border bg-background p-1 shadow-lg">
          {suggestions.length ? suggestions.map((user) => (
            <button key={user.id} type="button" onClick={() => insertMention(user)} className="block w-full rounded px-2 py-2 text-left text-sm hover:bg-muted">
              <span className="font-medium">{user.name || user.email}</span>
              <span className="block text-xs text-muted-foreground">{user.email}</span>
            </button>
          )) : <p className="px-2 py-2 text-xs text-muted-foreground">{token ? "No matching users" : "Search teammates"}</p>}
        </div>
      ) : null}
    </div>
  );
}

function MarkdownView({ value, className }: { value: string; className?: string }) {
  return <div className={cn("prose prose-sm max-w-none whitespace-normal", className)} dangerouslySetInnerHTML={{ __html: markdownToSafeHtml(value) }} />;
}

function markdownToSafeHtml(markdown: string) {
  const lines = escapeHtml(markdown || "").replace(/@\[([^\]]+)\]\(user:(\d+)\)/g, "<strong>@$1</strong>").split("\n");
  const html: string[] = [];
  let inCode = false;
  let inList = false;
  for (const line of lines) {
    if (line.trim().startsWith("```")) {
      if (inCode) {
        html.push("</code></pre>");
      } else {
        if (inList) {
          html.push("</ul>");
          inList = false;
        }
        html.push("<pre><code>");
      }
      inCode = !inCode;
      continue;
    }
    if (inCode) {
      html.push(`${line}\n`);
      continue;
    }
    const formatted = formatInlineMarkdown(line);
    if (line.startsWith("### ")) {
      if (inList) {
        html.push("</ul>");
        inList = false;
      }
      html.push(`<h3>${formatted.slice(4)}</h3>`);
    } else if (line.startsWith("## ")) {
      if (inList) {
        html.push("</ul>");
        inList = false;
      }
      html.push(`<h2>${formatted.slice(3)}</h2>`);
    } else if (line.startsWith("# ")) {
      if (inList) {
        html.push("</ul>");
        inList = false;
      }
      html.push(`<h1>${formatted.slice(2)}</h1>`);
    } else if (line.startsWith("- ")) {
      if (!inList) {
        html.push("<ul>");
        inList = true;
      }
      html.push(`<li>${formatted.slice(2)}</li>`);
    } else if (!line.trim()) {
      if (inList) {
        html.push("</ul>");
        inList = false;
      }
    } else {
      if (inList) {
        html.push("</ul>");
        inList = false;
      }
      html.push(`<p>${formatted}</p>`);
    }
  }
  if (inList) html.push("</ul>");
  if (inCode) html.push("</code></pre>");
  return html.join("");
}

function formatInlineMarkdown(value: string) {
  return value
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/_([^_]+)_/g, "<em>$1</em>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, (_match, label: string, href: string) => {
      const safeHref = sanitizeMarkdownUrl(href);
      return safeHref ? `<a href="${escapeHtmlAttribute(safeHref)}" target="_blank" rel="noreferrer noopener">${label}</a>` : label;
    });
}

function escapeHtml(value: string) {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

function escapeHtmlAttribute(value: string) {
  return escapeHtml(value).replace(/`/g, "&#096;");
}

function sanitizeMarkdownUrl(value: string) {
  const decoded = value.replace(/&amp;/g, "&").replace(/&quot;/g, "\"").replace(/&#039;/g, "'");
  try {
    const url = new URL(decoded);
    return ["http:", "https:"].includes(url.protocol) ? url.toString() : "";
  } catch {
    return "";
  }
}

const activityFilters: Array<{ key: ActivityFilter; label: string }> = [
  { key: "all", label: "All" },
  { key: "comments", label: "Comments" },
  { key: "changes", label: "Changes" },
  { key: "time", label: "Time logs" },
  { key: "files", label: "Files" },
];

function ActivityList({ items, filter, setFilter, sort, setSort }: { items: PMSActivity[]; filter: ActivityFilter; setFilter: (filter: ActivityFilter) => void; sort: ActivitySort; setSort: (sort: ActivitySort) => void }) {
  const visibleItems = items
    .filter((item) => activityMatchesFilter(item, filter))
    .sort((a, b) => {
      const first = new Date(a.created_at).getTime();
      const second = new Date(b.created_at).getTime();
      return sort === "desc" ? second - first : first - second;
    });
  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex flex-wrap gap-2">
          {activityFilters.map((item) => (
            <Button key={item.key} type="button" size="sm" variant={filter === item.key ? "default" : "outline"} onClick={() => setFilter(item.key)}>
              {item.label}
            </Button>
          ))}
        </div>
        <select value={sort} onChange={(event) => setSort(event.target.value as ActivitySort)} className="h-9 rounded-md border bg-background px-3 text-sm">
          <option value="desc">Newest first</option>
          <option value="asc">Oldest first</option>
        </select>
      </div>
      <div className="space-y-3">
        {visibleItems.map((item) => <ActivityTimelineItem key={item.id} item={item} />)}
        {!visibleItems.length ? <EmptyLine>No activity found for this filter.</EmptyLine> : null}
      </div>
    </div>
  );
}

function ActivityTimelineItem({ item }: { item: PMSActivity }) {
  const metadata = parseActivityMetadata(item.metadata_json);
  const Icon = activityIcon(item.action);
  return (
    <div className="relative flex gap-3 rounded-md border p-3 text-sm">
      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-semibold">{activityTitle(item)}</span>
          <Badge variant="outline">{item.action}</Badge>
        </div>
        <p className="mt-1 text-muted-foreground">{item.summary}</p>
        <p className="mt-2 text-xs text-muted-foreground">
          {item.actor_user_id ? `User #${item.actor_user_id}` : "System"} / {formatDateTime(item.created_at)}
        </p>
        {metadata ? <ActivityMetadata metadata={metadata} /> : null}
      </div>
    </div>
  );
}

function ActivityMetadata({ metadata }: { metadata: Record<string, unknown> }) {
  const field = String(metadata.field || "");
  const oldValue = metadata.old_value ?? metadata.oldValue;
  const newValue = metadata.new_value ?? metadata.newValue;
  if (field && (oldValue !== undefined || newValue !== undefined)) {
    return (
      <div className="mt-3 grid gap-2 rounded-md bg-muted/50 p-2 text-xs md:grid-cols-2">
        <div><span className="text-muted-foreground">Old {field}: </span>{formatActivityValue(oldValue)}</div>
        <div><span className="text-muted-foreground">New {field}: </span>{formatActivityValue(newValue)}</div>
      </div>
    );
  }
  if (Array.isArray(metadata.changed_fields) && metadata.changed_fields.length) {
    return <p className="mt-2 text-xs text-muted-foreground">Changed: {metadata.changed_fields.join(", ")}</p>;
  }
  if (metadata.body_preview) {
    return <p className="mt-2 rounded-md bg-muted/50 p-2 text-xs">{String(metadata.body_preview)}</p>;
  }
  if (metadata.duration_minutes) {
    return <p className="mt-2 text-xs text-muted-foreground">Duration: {formatMinutes(Number(metadata.duration_minutes))}</p>;
  }
  if (metadata.file_name || metadata.subtask_key) {
    return <p className="mt-2 text-xs text-muted-foreground">{String(metadata.file_name || metadata.subtask_key)}</p>;
  }
  return null;
}

function activityMatchesFilter(item: PMSActivity, filter: ActivityFilter) {
  if (filter === "all") return true;
  if (filter === "comments") return item.action.startsWith("comment.");
  if (filter === "time") return item.action.startsWith("time.");
  if (filter === "files") return item.action.startsWith("attachment.") || item.entity_type === "file";
  return item.action.includes("changed") || item.action === "task.updated" || item.action === "task.created" || item.action === "subtask.created" || item.action.startsWith("dependency.") || item.action.startsWith("checklist.");
}

function activityIcon(action: string) {
  if (action.startsWith("comment.")) return MessageSquare;
  if (action.startsWith("time.")) return Timer;
  if (action.startsWith("attachment.")) return Paperclip;
  if (action.startsWith("checklist.")) return CheckSquare;
  if (action.startsWith("dependency.")) return Link2;
  if (action.includes("date")) return CalendarDays;
  return GitBranch;
}

function activityTitle(item: PMSActivity) {
  return item.action
    .split(".")
    .map((part) => part.replace(/_/g, " "))
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function parseActivityMetadata(value?: string) {
  if (!value) return null;
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === "object" ? parsed as Record<string, unknown> : null;
  } catch {
    return null;
  }
}

function formatActivityValue(value: unknown) {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

type TimeTabProps = {
  logs: PMSTimeLog[];
  totalMinutes: number;
  billableMinutes: number;
  nonBillableMinutes: number;
  date: string;
  setDate: (value: string) => void;
  start: string;
  setStart: (value: string) => void;
  end: string;
  setEnd: (value: string) => void;
  minutes: string;
  setMinutes: (value: string) => void;
  description: string;
  setDescription: (value: string) => void;
  billable: boolean;
  setBillable: (value: boolean) => void;
  editingId: number | null;
  error: string | null;
  logTime: (event: FormEvent) => void;
  editTimeLog: (log: PMSTimeLog) => void;
  deleteTimeLog: (log: PMSTimeLog) => void;
  cancelEdit: () => void;
};

function TimeTab({
  logs,
  totalMinutes,
  billableMinutes,
  nonBillableMinutes,
  date,
  setDate,
  start,
  setStart,
  end,
  setEnd,
  minutes,
  setMinutes,
  description,
  setDescription,
  billable,
  setBillable,
  editingId,
  error,
  logTime,
  editTimeLog,
  deleteTimeLog,
  cancelEdit,
}: TimeTabProps) {
  return (
    <>
      <div className="grid gap-2 sm:grid-cols-3">
        <TimeTotal label="Total logged" value={totalMinutes} />
        <TimeTotal label="Billable" value={billableMinutes} />
        <TimeTotal label="Non-billable" value={nonBillableMinutes} />
      </div>
      {error ? <div className="rounded-md border border-red-200 bg-red-50 p-2 text-sm text-red-700">{error}</div> : null}
      <form onSubmit={logTime} className="rounded-md border p-3">
        <div className="grid gap-3 md:grid-cols-[9rem_8rem_8rem_8rem_1fr]">
          <Field label="Date"><Input type="date" value={date} onChange={(event) => setDate(event.target.value)} required /></Field>
          <Field label="Start"><Input type="time" value={start} onChange={(event) => setStart(event.target.value)} /></Field>
          <Field label="End"><Input type="time" value={end} onChange={(event) => setEnd(event.target.value)} /></Field>
          <Field label="Duration"><Input type="number" min="1" value={minutes} onChange={(event) => setMinutes(event.target.value)} required /></Field>
          <Field label="Description"><Input value={description} onChange={(event) => setDescription(event.target.value)} placeholder="What did you work on?" /></Field>
        </div>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
          <label className="inline-flex items-center gap-2 text-sm">
            <input type="checkbox" checked={billable} onChange={(event) => setBillable(event.target.checked)} />
            Billable
          </label>
          <div className="flex gap-2">
            {editingId ? <Button type="button" variant="outline" onClick={cancelEdit}>Cancel</Button> : null}
            <Button type="submit">{editingId ? "Save time log" : "Log time"}</Button>
          </div>
        </div>
      </form>
      <div className="space-y-2">
        {logs.map((item) => (
          <div key={item.id} className="rounded-md border p-3 text-sm">
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold">{formatMinutes(item.duration_minutes)}</span>
                  <Badge variant={item.is_billable ? "default" : "outline"}>{item.is_billable ? "Billable" : "Non-billable"}</Badge>
                  <Badge variant="outline">{item.approval_status}</Badge>
                </div>
                <p className="mt-2 text-muted-foreground">{item.description || "No description"}</p>
                <p className="mt-2 text-xs text-muted-foreground">
                  {formatDate(item.log_date)}
                  {item.start_time ? ` / ${formatTime(item.start_time)}` : ""}
                  {item.end_time ? ` - ${formatTime(item.end_time)}` : ""}
                </p>
              </div>
              <div className="flex gap-2">
                <Button type="button" size="sm" variant="outline" onClick={() => editTimeLog(item)}>Edit</Button>
                <Button type="button" size="sm" variant="ghost" onClick={() => deleteTimeLog(item)}>Delete</Button>
              </div>
            </div>
          </div>
        ))}
      </div>
      {!logs.length ? <EmptyLine>No time logged yet.</EmptyLine> : null}
    </>
  );
}

function TimeTotal({ label, value }: { label: string; value: number }) {
  return <div className="rounded-md bg-muted/50 p-3 text-sm"><p className="text-muted-foreground">{label}</p><p className="mt-1 font-semibold">{formatMinutes(value)}</p></div>;
}

function FilesTab({
  files,
  uploading,
  dragActive,
  setDragActive,
  error,
  uploadAttachments,
  deleteAttachment,
}: {
  files: PMSFileAsset[];
  uploading: boolean;
  dragActive: boolean;
  setDragActive: (value: boolean) => void;
  error: string | null;
  uploadAttachments: (files: FileList | File[]) => void;
  deleteAttachment: (file: PMSFileAsset) => void;
}) {
  const [previewFile, setPreviewFile] = useState<PMSFileAsset | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  useEffect(() => {
    let objectUrl: string | null = null;
    if (!previewFile) {
      setPreviewUrl(null);
      return;
    }
    setPreviewLoading(true);
    filesAPI.downloadBlob(previewFile.id)
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob);
        setPreviewUrl(objectUrl);
      })
      .catch(() => setPreviewUrl(null))
      .finally(() => setPreviewLoading(false));
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [previewFile]);

  const handleDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setDragActive(false);
    uploadAttachments(event.dataTransfer.files);
  };

  const openAttachment = async (file: PMSFileAsset) => {
    const blob = await filesAPI.downloadBlob(file.id);
    const url = URL.createObjectURL(blob);
    window.open(url, "_blank", "noopener,noreferrer");
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
  };

  const downloadAttachment = async (file: PMSFileAsset) => {
    const blob = await filesAPI.downloadBlob(file.id);
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = file.original_name || file.file_name;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  };

  const canPreview = (file: PMSFileAsset) => {
    const type = file.mime_type || "";
    return type.startsWith("image/") || type === "application/pdf";
  };

  return (
    <div className="space-y-4">
      <label
        className={cn(
          "flex min-h-36 cursor-pointer flex-col items-center justify-center rounded-md border border-dashed p-6 text-center transition-colors",
          dragActive ? "border-primary bg-primary/5" : "border-muted-foreground/30 bg-muted/20",
          uploading ? "pointer-events-none opacity-70" : ""
        )}
        onDragEnter={(event) => {
          event.preventDefault();
          setDragActive(true);
        }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={() => setDragActive(false)}
        onDrop={handleDrop}
      >
        <Upload className="mb-3 h-7 w-7 text-muted-foreground" />
        <span className="font-medium">{uploading ? "Uploading attachments..." : "Drop files here or choose files"}</span>
        <span className="mt-1 text-xs text-muted-foreground">Images, PDFs, Office docs, text, CSV, and ZIP files up to 25 MB.</span>
        <Input
          type="file"
          multiple
          className="hidden"
          disabled={uploading}
          onChange={(event) => {
            if (event.target.files) uploadAttachments(event.target.files);
            event.currentTarget.value = "";
          }}
        />
      </label>
      {error ? <p className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p> : null}
      <div className="space-y-2">
        {files.map((item) => (
          <div key={item.id} className="rounded-md border p-3">
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <div className="flex min-w-0 gap-3">
                <FileTypeIcon mimeType={item.mime_type} />
                <div className="min-w-0">
                  <p className="truncate font-medium">{item.original_name || item.file_name}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {item.mime_type || "Unknown type"} - {formatBytes(item.size_bytes)} - Uploaded by {item.uploaded_by_name || userLabel(item.uploaded_by_user_id, "Unknown")} - {formatDateTime(item.created_at)}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {canPreview(item) ? (
                  <Button type="button" size="sm" variant="outline" onClick={() => setPreviewFile((current) => current?.id === item.id ? null : item)}>
                    <Eye className="h-4 w-4" />Preview
                  </Button>
                ) : null}
                <Button type="button" size="sm" variant="outline" onClick={() => openAttachment(item)}>
                  <FileIcon className="h-4 w-4" />Open
                </Button>
                <Button type="button" size="sm" variant="outline" onClick={() => downloadAttachment(item)}>
                  <Download className="h-4 w-4" />Download
                </Button>
                <Button type="button" size="sm" variant="ghost" onClick={() => deleteAttachment(item)}>
                  <Trash2 className="h-4 w-4" />Delete
                </Button>
              </div>
            </div>
            {previewFile?.id === item.id ? (
              <div className="mt-3 overflow-hidden rounded-md border bg-muted/20">
                {previewLoading ? <div className="p-4 text-sm text-muted-foreground">Loading preview...</div> : null}
                {!previewLoading && previewUrl && (item.mime_type || "").startsWith("image/") ? <img src={previewUrl} alt={item.original_name} className="max-h-96 w-full object-contain" /> : null}
                {!previewLoading && previewUrl && item.mime_type === "application/pdf" ? <iframe title={item.original_name} src={previewUrl} className="h-96 w-full" /> : null}
                {!previewLoading && !previewUrl ? <div className="p-4 text-sm text-muted-foreground">Preview unavailable.</div> : null}
              </div>
            ) : null}
          </div>
        ))}
      </div>
      {!files.length ? <EmptyLine>No files attached yet.</EmptyLine> : null}
    </div>
  );
}

function FileTypeIcon({ mimeType }: { mimeType?: string }) {
  const className = "mt-0.5 h-5 w-5 shrink-0 text-muted-foreground";
  if ((mimeType || "").startsWith("image/")) return <ImageIcon className={className} />;
  if (mimeType === "application/pdf" || (mimeType || "").startsWith("text/")) return <FileText className={className} />;
  if ((mimeType || "").includes("zip")) return <FileArchive className={className} />;
  return <FileIcon className={className} />;
}

function LinksTab({
  links,
  currentTaskId,
  dependencyId,
  setDependencyId,
  dependencyError,
  addDependency,
}: {
  links: PMSTaskDependency[];
  currentTaskId: number;
  dependencyId: string;
  setDependencyId: (value: string) => void;
  dependencyError: string | null;
  addDependency: (event: FormEvent) => void;
}) {
  return (
    <>
      <form onSubmit={addDependency} className="rounded-md border p-3">
        <div className="grid gap-2 md:grid-cols-[1fr_auto]">
          <Input type="number" min="1" value={dependencyId} onChange={(event) => setDependencyId(event.target.value)} placeholder="Link blocker by task ID" />
          <Button type="submit"><Link2 className="h-4 w-4" />Add blocker</Button>
        </div>
        {dependencyError ? <p className="mt-2 text-sm text-red-600">{dependencyError}</p> : null}
      </form>
      {links.map((item) => {
        const isBlockedBy = item.task_id === currentTaskId;
        return (
          <TimelineCard
            key={item.id}
            title={isBlockedBy ? `${item.depends_on_task_key || `Task #${item.depends_on_task_id}`} blocks this task` : `This task blocks ${item.task_key || `Task #${item.task_id}`}`}
            meta={isBlockedBy ? item.depends_on_task_title || item.dependency_type : item.task_title || item.dependency_type}
          />
        );
      })}
      {!links.length ? <EmptyLine>No linked tasks yet.</EmptyLine> : null}
    </>
  );
}

function DevelopmentTab({ links }: { links: PMSDevLink[] }) {
  const grouped = {
    branch: links.filter((item) => item.link_type === "branch"),
    commit: links.filter((item) => item.link_type === "commit"),
    pr: links.filter((item) => item.link_type === "pr"),
    mr: links.filter((item) => item.link_type === "mr"),
  };
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-4">
        <DevMetric label="Branches" value={grouped.branch.length} />
        <DevMetric label="Commits" value={grouped.commit.length} />
        <DevMetric label="PRs" value={grouped.pr.length} />
        <DevMetric label="MRs" value={grouped.mr.length} />
      </div>
      {(["pr", "mr", "commit", "branch"] as PMSDevLink["link_type"][]).map((kind) => (
        <div key={kind} className="space-y-2">
          <h3 className="text-sm font-semibold uppercase text-muted-foreground">{kind === "pr" ? "Pull requests" : kind === "mr" ? "Merge requests" : kind === "commit" ? "Commits" : "Branches"}</h3>
          {grouped[kind].map((item) => (
            <a key={item.id} href={item.url || "#"} target="_blank" rel="noreferrer" className="block rounded-md border p-3 hover:bg-muted/50">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="text-xs font-semibold text-primary">{item.provider} / {item.link_type} / {item.external_id}</p>
                  <h4 className="font-medium">{item.title || item.external_id}</h4>
                </div>
                <Badge variant="outline">{item.status || "linked"}</Badge>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">{item.author || "Unknown author"} / {formatDateTime(item.updated_at || item.created_at)}</p>
            </a>
          ))}
        </div>
      ))}
      {!links.length ? <EmptyLine>No development activity linked yet. Configure a GitHub or GitLab repository in PMS settings and include this task key in branches, commits, PRs, or MRs.</EmptyLine> : null}
    </div>
  );
}

function DevMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md bg-muted/50 p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-xl font-semibold">{value}</p>
    </div>
  );
}

function TimelineCard({ title, meta }: { title: ReactNode; meta: ReactNode }) {
  return <div className="rounded-md border p-3 text-sm"><p>{title}</p><p className="mt-2 text-xs text-muted-foreground">{meta}</p></div>;
}

function userLabel(userId: number | undefined, fallback: string) {
  return userId ? `User #${userId}` : fallback;
}

function formatMinutes(minutes: number) {
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (!hours) return `${mins}m`;
  return `${hours}h ${mins}m`;
}

function formatTime(value: string) {
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function formatBytes(bytes: number) {
  if (!bytes) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
