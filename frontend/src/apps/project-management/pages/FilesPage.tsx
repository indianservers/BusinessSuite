import { usePageRefresh } from "@/lib/page-refresh";
import type React from "react";
import { FormEvent, useEffect, useState } from "react";
import { FileText, Upload } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatDate } from "@/lib/utils";
import { filesAPI, projectsAPI } from "../services/api";
import type { FileVisibility, PMSFileAsset, PMSProject } from "../types";

export default function FilesPage() {
  const [projects, setProjects] = useState<PMSProject[]>([]);
  const [files, setFiles] = useState<PMSFileAsset[]>([]);
  const [projectId, setProjectId] = useState("");
  const [fileName, setFileName] = useState("");
  const [visibility, setVisibility] = useState<FileVisibility>("Project Team");

  useEffect(() => {
    projectsAPI.list().then((items) => {
      setProjects(items);
      const firstId = String(items[0]?.id || "");
      setProjectId(firstId);
      filesAPI.list(firstId ? { project_id: Number(firstId) } : undefined).then(setFiles);
    });
  }, []);

  usePageRefresh(async () => {
    setProjects(await projectsAPI.list());
    await filesAPI.list(projectId ? { project_id: Number(projectId) } : undefined).then(setFiles);
  });

  const switchProject = (value: string) => {
    setProjectId(value);
    filesAPI.list(value ? { project_id: Number(value) } : undefined).then(setFiles);
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!projectId || !fileName.trim()) return;
    const created = await filesAPI.create({
      project_id: Number(projectId),
      file_name: fileName,
      original_name: fileName,
      mime_type: "application/octet-stream",
      size_bytes: 0,
      storage_path: `metadata://${fileName}`,
      visibility,
    });
    setFiles((items) => [created, ...items]);
    setFileName("");
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">Files</h1>
        <p className="page-description">File metadata, visibility, and project attachment management.</p>
      </div>
      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><Upload className="h-5 w-5" />Add file metadata</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={submit} className="grid gap-4 md:grid-cols-[1fr_1fr_12rem_auto] md:items-end">
            <Field label="Project"><select value={projectId} onChange={(event) => switchProject(event.target.value)} className="h-10 w-full rounded-md border bg-background px-3 text-sm">{projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select></Field>
            <Field label="File name"><Input value={fileName} onChange={(event) => setFileName(event.target.value)} placeholder="Scope-v2.pdf" /></Field>
            <Field label="Visibility"><select value={visibility} onChange={(event) => setVisibility(event.target.value as FileVisibility)} className="h-10 w-full rounded-md border bg-background px-3 text-sm">{["Internal", "Project Team", "Client Visible", "Private"].map((item) => <option key={item}>{item}</option>)}</select></Field>
            <Button type="submit">Add</Button>
          </form>
        </CardContent>
      </Card>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {files.map((file) => (
          <Card key={file.id}>
            <CardContent className="flex items-start gap-4 p-5">
              <div className="rounded-lg bg-blue-100 p-3 text-blue-700"><FileText className="h-5 w-5" /></div>
              <div className="min-w-0 flex-1">
                <h2 className="truncate font-semibold">{file.original_name}</h2>
                <p className="mt-1 text-sm text-muted-foreground">Version {file.version_number} - {formatDate(file.created_at)}</p>
                <Badge variant="outline" className="mt-3">{file.visibility}</Badge>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="space-y-2"><Label>{label}</Label>{children}</div>;
}

