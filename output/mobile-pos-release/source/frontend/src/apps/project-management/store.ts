/**
 * KaryaFlow Zustand Store
 * Global state management for project management
 */
import { create } from "zustand";
import {
  PMSProject,
  PMSTask,
  PMSBoard,
  PMSComment,
  ProjectFilters,
  TaskFilters,
} from "./types";

// ============= PROJECT STORE =============
interface ProjectStore {
  projects: PMSProject[];
  selectedProject: PMSProject | null;
  loading: boolean;
  filters: ProjectFilters;

  setProjects: (projects: PMSProject[]) => void;
  setSelectedProject: (project: PMSProject | null) => void;
  setLoading: (loading: boolean) => void;
  setFilters: (filters: ProjectFilters) => void;
  addProject: (project: PMSProject) => void;
  updateProject: (project: PMSProject) => void;
  removeProject: (projectId: number) => void;
}

export const useProjectStore = create<ProjectStore>((set) => ({
  projects: [],
  selectedProject: null,
  loading: false,
  filters: {},

  setProjects: (projects) => set({ projects }),
  setSelectedProject: (project) => set({ selectedProject: project }),
  setLoading: (loading) => set({ loading }),
  setFilters: (filters) => set({ filters }),

  addProject: (project) =>
    set((state) => ({ projects: [...state.projects, project] })),

  updateProject: (project) =>
    set((state) => ({
      projects: state.projects.map((p) => (p.id === project.id ? project : p)),
      selectedProject:
        state.selectedProject?.id === project.id ? project : state.selectedProject,
    })),

  removeProject: (projectId) =>
    set((state) => ({
      projects: state.projects.filter((p) => p.id !== projectId),
      selectedProject:
        state.selectedProject?.id === projectId ? null : state.selectedProject,
    })),
}));

// ============= TASK STORE =============
interface TaskStore {
  tasks: PMSTask[];
  selectedTask: PMSTask | null;
  loading: boolean;
  filters: TaskFilters;

  setTasks: (tasks: PMSTask[]) => void;
  setSelectedTask: (task: PMSTask | null) => void;
  setLoading: (loading: boolean) => void;
  setFilters: (filters: TaskFilters) => void;
  addTask: (task: PMSTask) => void;
  updateTask: (task: PMSTask) => void;
  removeTask: (taskId: number) => void;
  reorderTask: (taskId: number, columnId: number, position: number) => void;
}

export const useTaskStore = create<TaskStore>((set) => ({
  tasks: [],
  selectedTask: null,
  loading: false,
  filters: {},

  setTasks: (tasks) => set({ tasks }),
  setSelectedTask: (task) => set({ selectedTask: task }),
  setLoading: (loading) => set({ loading }),
  setFilters: (filters) => set({ filters }),

  addTask: (task) => set((state) => ({ tasks: [...state.tasks, task] })),

  updateTask: (task) =>
    set((state) => ({
      tasks: state.tasks.map((t) => (t.id === task.id ? task : t)),
      selectedTask:
        state.selectedTask?.id === task.id ? task : state.selectedTask,
    })),

  removeTask: (taskId) =>
    set((state) => ({
      tasks: state.tasks.filter((t) => t.id !== taskId),
      selectedTask:
        state.selectedTask?.id === taskId ? null : state.selectedTask,
    })),

  reorderTask: (taskId, columnId, position) =>
    set((state) => ({
      tasks: state.tasks.map((t) =>
        t.id === taskId ? { ...t, column_id: columnId, position } : t
      ),
    })),
}));

// ============= KANBAN STORE =============
interface KanbanStore {
  board: PMSBoard | null;
  loading: boolean;
  expandedColumns: Set<number>;

  setBoard: (board: PMSBoard | null) => void;
  setLoading: (loading: boolean) => void;
  toggleColumnExpanded: (columnId: number) => void;
  expandColumn: (columnId: number) => void;
  collapseColumn: (columnId: number) => void;
  expandAllColumns: () => void;
  collapseAllColumns: () => void;
}

export const useKanbanStore = create<KanbanStore>((set) => ({
  board: null,
  loading: false,
  expandedColumns: new Set(),

  setBoard: (board) => set({ board }),
  setLoading: (loading) => set({ loading }),

  toggleColumnExpanded: (columnId) =>
    set((state) => {
      const newSet = new Set(state.expandedColumns);
      if (newSet.has(columnId)) {
        newSet.delete(columnId);
      } else {
        newSet.add(columnId);
      }
      return { expandedColumns: newSet };
    }),

  expandColumn: (columnId) =>
    set((state) => {
      const newSet = new Set(state.expandedColumns);
      newSet.add(columnId);
      return { expandedColumns: newSet };
    }),

  collapseColumn: (columnId) =>
    set((state) => {
      const newSet = new Set(state.expandedColumns);
      newSet.delete(columnId);
      return { expandedColumns: newSet };
    }),

  expandAllColumns: () =>
    set((state) => {
      const newSet = new Set(state.expandedColumns);
      state.board?.columns?.forEach((col) => newSet.add(col.id));
      return { expandedColumns: newSet };
    }),

  collapseAllColumns: () => set({ expandedColumns: new Set() }),
}));

// ============= COMMENTS STORE (COLLABORATION) =============
interface CommentsStore {
  commentsByTaskId: Map<number, PMSComment[]>;
  loading: boolean;

  setComments: (taskId: number, comments: PMSComment[]) => void;
  addComment: (taskId: number, comment: PMSComment) => void;
  updateComment: (taskId: number, comment: PMSComment) => void;
  removeComment: (taskId: number, commentId: number) => void;
  setLoading: (loading: boolean) => void;
}

export const useCommentsStore = create<CommentsStore>((set) => ({
  commentsByTaskId: new Map(),
  loading: false,

  setComments: (taskId, comments) =>
    set((state) => {
      const newMap = new Map(state.commentsByTaskId);
      newMap.set(taskId, comments);
      return { commentsByTaskId: newMap };
    }),

  addComment: (taskId, comment) =>
    set((state) => {
      const newMap = new Map(state.commentsByTaskId);
      const existing = newMap.get(taskId) || [];
      newMap.set(taskId, [...existing, comment]);
      return { commentsByTaskId: newMap };
    }),

  updateComment: (taskId, comment) =>
    set((state) => {
      const newMap = new Map(state.commentsByTaskId);
      const existing = newMap.get(taskId) || [];
      newMap.set(
        taskId,
        existing.map((c) => (c.id === comment.id ? comment : c))
      );
      return { commentsByTaskId: newMap };
    }),

  removeComment: (taskId, commentId) =>
    set((state) => {
      const newMap = new Map(state.commentsByTaskId);
      const existing = newMap.get(taskId) || [];
      newMap.set(taskId, existing.filter((c) => c.id !== commentId));
      return { commentsByTaskId: newMap };
    }),

  setLoading: (loading) => set({ loading }),
}));

// ============= UI STORE =============
interface UIStore {
  sidebarOpen: boolean;
  darkMode: boolean;
  selectedView: "list" | "board" | "calendar" | "gantt";
  showCreateTaskModal: boolean;
  showProjectModal: boolean;
  selectedTaskId: number | null;

  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;
  setDarkMode: (dark: boolean) => void;
  toggleDarkMode: () => void;
  setSelectedView: (view: "list" | "board" | "calendar" | "gantt") => void;
  setShowCreateTaskModal: (show: boolean) => void;
  setShowProjectModal: (show: boolean) => void;
  setSelectedTaskId: (id: number | null) => void;
}

export const useUIStore = create<UIStore>((set) => ({
  sidebarOpen: true,
  darkMode: false,
  selectedView: "board",
  showCreateTaskModal: false,
  showProjectModal: false,
  selectedTaskId: null,

  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  toggleSidebar: () =>
    set((state) => ({ sidebarOpen: !state.sidebarOpen })),

  setDarkMode: (dark) => set({ darkMode: dark }),
  toggleDarkMode: () =>
    set((state) => ({ darkMode: !state.darkMode })),

  setSelectedView: (view) => set({ selectedView: view }),
  setShowCreateTaskModal: (show) => set({ showCreateTaskModal: show }),
  setShowProjectModal: (show) => set({ showProjectModal: show }),
  setSelectedTaskId: (id) => set({ selectedTaskId: id }),
}));

