import React, { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, ClipboardList, Kanban, Plus, Send } from "lucide-react";
import { canAccessRoute } from "@/lib/roles";
import { useAuthStore } from "@/store/authStore";
import { useProjectStore, useUIStore } from "./store";
import { projectIntakeAPI, projectsAPI } from "./services/api";
import { PMSProject, PMSProjectIntake } from "./types";

/**
 * KaryaFlow - Project Management Home Page
 * Main dashboard and entry point
 */
const ProjectManagementHomePage: React.FC = () => {
  const navigate = useNavigate();
  const { projects, setProjects, setSelectedProject } = useProjectStore();
  const { setSidebarOpen } = useUIStore();
  const { user } = useAuthStore();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [intakes, setIntakes] = useState<PMSProjectIntake[]>([]);
  const [intakeTitle, setIntakeTitle] = useState("");
  const [intakeDescription, setIntakeDescription] = useState("");
  const [intakePriority, setIntakePriority] = useState("Medium");
  const [intakeSaving, setIntakeSaving] = useState(false);

  // Initialize sidebar state
  useEffect(() => {
    setSidebarOpen(true);
  }, [setSidebarOpen]);

  // Load projects on mount
  useEffect(() => {
    const loadProjects = async () => {
      try {
        setLoading(true);
        const data = await projectsAPI.list(0, 100);
        const intakeData = await projectIntakeAPI.list(undefined, 0, 10).catch(() => []);
        setProjects(data || []);
        setIntakes(intakeData || []);
      } catch (err: any) {
        setError(err.message || "Failed to load projects");
        console.error("Error loading projects:", err);
      } finally {
        setLoading(false);
      }
    };

    loadProjects();
  }, [setProjects]);

  const handleSelectProject = (project: PMSProject) => {
    setSelectedProject(project);
    navigate(`/pms/projects/${project.id}`);
  };

  const handleCreateProject = () => {
    navigate("/pms/projects/new");
  };
  const canCreateProject = canAccessRoute("/pms/projects/new", user?.role, user?.is_superuser);
  const workflows = [
    { title: "Manage tasks", description: "Assign work and track delivery.", path: "/pms/tasks" },
    { title: "Plan sprints", description: "Organize upcoming work and priorities.", path: "/pms/sprints" },
    { title: "Review timesheets", description: "Track time and review submissions.", path: "/pms/timesheets" },
    { title: "Review risks", description: "Resolve blockers and delivery risks.", path: "/pms/risk-register" },
  ].filter((workflow) => canAccessRoute(workflow.path, user?.role, user?.is_superuser));

  const handleSubmitIntake = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!intakeTitle.trim()) return;
    try {
      setIntakeSaving(true);
      setError(null);
      const intake = await projectIntakeAPI.create({
        title: intakeTitle.trim(),
        description: intakeDescription.trim() || undefined,
        priority: intakePriority,
      });
      setIntakes((items) => [intake, ...items]);
      setIntakeTitle("");
      setIntakeDescription("");
      setIntakePriority("Medium");
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || "Failed to submit project intake");
    } finally {
      setIntakeSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading KaryaFlow...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="bg-blue-600 p-3 rounded-lg">
                <Kanban className="text-white" size={32} />
              </div>
              <div>
                <h1 className="text-4xl font-bold text-gray-900">KaryaFlow</h1>
                <p className="text-gray-500 mt-1">Project Management & Collaboration Platform</p>
              </div>
            </div>
            {canCreateProject ? (
              <button
                onClick={handleCreateProject}
                className="bg-gradient-to-r from-blue-600 to-blue-700 text-white px-6 py-3 rounded-lg hover:shadow-lg transition-all flex items-center gap-2 font-medium"
              >
                <Plus size={20} />
                New Project
              </button>
            ) : null}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {workflows.length > 0 && (
          <section className="mb-8" aria-labelledby="pms-workflows">
            <h2 id="pms-workflows" className="mb-3 text-lg font-bold text-gray-900">Workflows</h2>
            <div className="divide-y divide-gray-100 rounded-xl border bg-white px-5">
              {workflows.map((workflow) => (
                <Link key={workflow.path} to={workflow.path} className="group flex items-center justify-between gap-4 py-4 text-sm">
                  <div>
                    <p className="font-semibold text-gray-900 group-hover:text-blue-600">{workflow.title}</p>
                    <p className="mt-1 text-gray-500">{workflow.description}</p>
                  </div>
                  <ArrowRight className="h-4 w-4 shrink-0 text-blue-600" />
                </Link>
              ))}
            </div>
          </section>
        )}

        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-red-800 font-medium">{error}</p>
          </div>
        )}

        <details className="mb-8 rounded-xl border bg-white p-5 shadow-sm">
          <summary className="cursor-pointer text-sm font-semibold text-gray-900">Project intake - Submit or review requests</summary>
          <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_24rem]">
          <form onSubmit={handleSubmitIntake} className="rounded-xl border bg-white p-5 shadow-sm">
            <div className="mb-4 flex items-center gap-2">
              <ClipboardList className="h-5 w-5 text-blue-700" />
              <h2 className="text-lg font-bold text-gray-900">Project Intake</h2>
            </div>
            <div className="grid gap-3 md:grid-cols-[1fr_12rem]">
              <input
                aria-label="Project request title"
                value={intakeTitle}
                onChange={(event) => setIntakeTitle(event.target.value)}
                className="h-11 rounded-lg border border-gray-300 px-3 text-sm"
                placeholder="Project request title"
              />
              <select
                aria-label="Project request priority"
                value={intakePriority}
                onChange={(event) => setIntakePriority(event.target.value)}
                className="h-11 rounded-lg border border-gray-300 px-3 text-sm"
              >
                <option>Low</option>
                <option>Medium</option>
                <option>High</option>
                <option>Critical</option>
              </select>
            </div>
            <textarea
              aria-label="Project request description"
              value={intakeDescription}
              onChange={(event) => setIntakeDescription(event.target.value)}
              className="mt-3 min-h-24 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
              placeholder="Short description, goal, or business need"
            />
            <button
              type="submit"
              disabled={intakeSaving || !intakeTitle.trim()}
              className="mt-3 inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
            >
              <Send className="h-4 w-4" />
              {intakeSaving ? "Submitting..." : "Submit Intake"}
            </button>
          </form>
          <div className="rounded-xl border bg-white p-5 shadow-sm">
            <h2 className="text-lg font-bold text-gray-900">Recent Intakes</h2>
            <div className="mt-3 space-y-3">
              {intakes.slice(0, 4).map((intake) => (
                <div key={intake.id} className="rounded-lg border border-gray-200 p-3">
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-sm font-semibold text-gray-900">{intake.title}</p>
                    <span className="rounded-full bg-gray-100 px-2 py-1 text-xs font-semibold text-gray-700">{intake.status}</span>
                  </div>
                  <p className="mt-1 text-xs text-gray-500">{intake.priority} priority</p>
                </div>
              ))}
              {!intakes.length ? <p className="text-sm text-gray-500">No intake requests submitted yet.</p> : null}
            </div>
          </div>
        </div>

        </details>
        <div className="mb-4 flex items-center justify-between gap-4">
          <h2 className="text-lg font-bold text-gray-900">Projects</h2>
          {canAccessRoute("/pms/projects", user?.role, user?.is_superuser) && (
            <Link to="/pms/projects" className="text-sm font-medium text-blue-600 hover:underline">View all projects</Link>
          )}
        </div>
        {projects.length === 0 ? (
          <div className="bg-white rounded-xl border-2 border-dashed border-gray-300 p-16 text-center shadow-sm">
            <Kanban className="mx-auto h-16 w-16 text-gray-300 mb-4" />
            <h3 className="text-2xl font-bold text-gray-900 mb-2">
              No projects yet
            </h3>
            <p className="text-gray-600 mb-8 max-w-md mx-auto">
              Create your first project to get started with KaryaFlow's powerful project management capabilities.
            </p>
            {canCreateProject ? (
              <button
                onClick={handleCreateProject}
                className="bg-gradient-to-r from-blue-600 to-blue-700 text-white px-8 py-3 rounded-lg hover:shadow-lg transition-all inline-flex items-center gap-2 font-medium"
              >
                <Plus size={20} />
                Create Your First Project
              </button>
            ) : null}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {projects.slice(0, 6).map((project) => (
              <button
                type="button"
                key={project.id}
                onClick={() => handleSelectProject(project)}
                className="bg-white rounded-xl shadow-sm hover:shadow-lg transition-all cursor-pointer p-6 text-left border-l-4 border-blue-600 group"
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <h3 className="text-lg font-bold text-gray-900 group-hover:text-blue-600 transition-colors">
                      {project.name}
                    </h3>
                    <p className="text-sm text-gray-500">{project.project_key}</p>
                  </div>
                  <span className={`px-3 py-1 rounded-full text-xs font-semibold flex-shrink-0 ml-2 ${
                    project.status === "Active"
                      ? "bg-green-100 text-green-800"
                      : project.status === "Completed"
                      ? "bg-blue-100 text-blue-800"
                      : "bg-gray-100 text-gray-800"
                  }`}>
                    {project.status}
                  </span>
                </div>

                {project.description && (
                  <p className="text-sm text-gray-600 mb-4 line-clamp-2">
                    {project.description}
                  </p>
                )}

                <div className="flex items-center justify-between mb-4">
                  <div className="text-sm">
                    <div className="text-gray-500 text-xs">Progress</div>
                    <div className="text-2xl font-bold text-gray-900">
                      {project.progress_percent}%
                    </div>
                  </div>
                  <div className="w-24 h-3 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-blue-500 to-blue-600 transition-all duration-300"
                      style={{ width: `${project.progress_percent}%` }}
                    />
                  </div>
                </div>

                <div className="flex items-center justify-between pt-4 border-t border-gray-100">
                  {project.due_date && (
                    <div className="text-xs text-gray-500">
                      Due: {new Date(project.due_date).toLocaleDateString()}
                    </div>
                  )}
                  <div className="text-xs font-medium text-blue-600 group-hover:text-blue-700">
                    View {">"}
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}


      </div>
    </div>
  );
};

export default ProjectManagementHomePage;

