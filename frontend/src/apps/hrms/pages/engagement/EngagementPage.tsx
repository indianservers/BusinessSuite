import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Megaphone, Plus, RefreshCw, Send, Smile, Trophy } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { getRoleKey } from "@/lib/roles";
import { employeeApi, engagementApi, reportsApi } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { usePageTitle } from "@/hooks/use-page-title";
import { formatDate } from "@/lib/utils";

export default function EngagementPage() {
  usePageTitle("Engagement");
  const qc = useQueryClient();
  const { toast } = useToast();
  const user = useAuthStore((state) => state.user);
  const roleKey = getRoleKey(user?.role, user?.is_superuser);
  const canManageEngagement = roleKey === "admin" || roleKey === "hr";
  const [announcement, setAnnouncement] = useState({ title: "", body: "" });
  const [pollTitle, setPollTitle] = useState("Preferred Friday outing");
  const [pollOptions, setPollOptions] = useState("Restaurant,Park");
  const [selectedSurveyId, setSelectedSurveyId] = useState<number | null>(null);
  const [selectedOption, setSelectedOption] = useState("");
  const [recognition, setRecognition] = useState({ to_employee_id: "", title: "", message: "", badge: "Team shoutout" });

  const announcements = useQuery({ queryKey: ["engagement-announcements"], queryFn: () => engagementApi.announcements(false).then((r) => r.data) });
  const surveys = useQuery({ queryKey: ["engagement-surveys"], queryFn: () => engagementApi.surveys(false).then((r) => r.data) });
  const recognitions = useQuery({ queryKey: ["recognition-wall"], queryFn: () => engagementApi.recognitions().then((r) => r.data) });
  const employees = useQuery({ queryKey: ["engagement-employees"], queryFn: () => employeeApi.list({ per_page: 100 }).then((r) => r.data.items || []) });
  const moments = useQuery({ queryKey: ["people-moments", 14], queryFn: () => reportsApi.peopleMoments(14).then((r) => r.data) });
  const activeSurvey = surveys.data?.find((item: any) => item.id === selectedSurveyId) || surveys.data?.[0];
  const resultSurveyId = selectedSurveyId || activeSurvey?.id;
  const results = useQuery({
    queryKey: ["survey-results", resultSurveyId],
    queryFn: () => engagementApi.surveyResults(resultSurveyId!).then((r) => r.data),
    enabled: !!resultSurveyId,
  });

  const createAnnouncement = useMutation({
    mutationFn: () => engagementApi.createAnnouncement({ ...announcement, audience: "All", is_published: true }),
    onSuccess: () => {
      setAnnouncement({ title: "", body: "" });
      qc.invalidateQueries({ queryKey: ["engagement-announcements"] });
      toast({ title: "Announcement published" });
    },
  });
  const createPoll = useMutation({
    mutationFn: () => engagementApi.createSurvey({
      title: pollTitle,
      survey_type: "Poll",
      question: pollTitle,
      options_json: pollOptions.split(",").map((item) => item.trim()).filter(Boolean),
      status: "Open",
    }),
    onSuccess: (response) => {
      setSelectedSurveyId(response.data.id);
      qc.invalidateQueries({ queryKey: ["engagement-surveys"] });
      toast({ title: "Poll created" });
    },
  });
  const vote = useMutation({
    mutationFn: () => engagementApi.submitSurveyResponse({ survey_id: resultSurveyId, comments: selectedOption }),
    onSuccess: () => {
      setSelectedOption("");
      qc.invalidateQueries({ queryKey: ["survey-results"] });
      toast({ title: "Vote submitted" });
    },
  });
  const createRecognition = useMutation({
    mutationFn: () => engagementApi.createRecognition({ ...recognition, to_employee_id: Number(recognition.to_employee_id), is_public: true, points: 10 }),
    onSuccess: () => {
      setRecognition({ to_employee_id: "", title: "", message: "", badge: "Team shoutout" });
      qc.invalidateQueries({ queryKey: ["recognition-wall"] });
      toast({ title: "Recognition posted" });
    },
  });

  const options = activeSurvey?.options_json || [];

  return (
    <div className="space-y-5">
      <div className="rounded-lg border bg-card p-5">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Engagement</p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Announcements & Engagement</h1>
        <p className="mt-1 text-sm text-muted-foreground">Pinned announcements, pulse polls, recognition wall, and people moment notifications.</p>
      </div>

      {announcements.data?.filter((item: any) => item.is_published).slice(0, 1).map((item: any) => (
        <div key={item.id} className="rounded-lg border border-primary/30 bg-primary/5 p-4">
          <div className="flex items-start gap-3">
            <Megaphone className="mt-1 h-5 w-5 text-primary" />
            <div>
              <p className="font-semibold">{item.title}</p>
              <p className="text-sm text-muted-foreground">{item.body}</p>
            </div>
          </div>
        </div>
      ))}

      <div className="grid gap-4 xl:grid-cols-3">
        {canManageEngagement && <Card>
          <CardHeader><CardTitle className="text-base">Post Announcement</CardTitle></CardHeader>
          <CardContent>
            <form className="space-y-3" onSubmit={(e: FormEvent) => { e.preventDefault(); createAnnouncement.mutate(); }}>
              <div className="space-y-2"><Label>Title</Label><Input value={announcement.title} onChange={(e) => setAnnouncement({ ...announcement, title: e.target.value })} required /></div>
              <div className="space-y-2"><Label>Message</Label><Input value={announcement.body} onChange={(e) => setAnnouncement({ ...announcement, body: e.target.value })} required /></div>
              <Button type="submit" disabled={createAnnouncement.isPending}><Send className="h-4 w-4" />Publish</Button>
            </form>
          </CardContent>
        </Card>}

        {canManageEngagement && <Card>
          <CardHeader><CardTitle className="text-base">Create Poll</CardTitle></CardHeader>
          <CardContent>
            <form className="space-y-3" onSubmit={(e: FormEvent) => { e.preventDefault(); createPoll.mutate(); }}>
              <div className="space-y-2"><Label>Question</Label><Input value={pollTitle} onChange={(e) => setPollTitle(e.target.value)} required /></div>
              <div className="space-y-2"><Label>Options</Label><Input value={pollOptions} onChange={(e) => setPollOptions(e.target.value)} required /></div>
              <Button type="submit" disabled={createPoll.isPending}><Plus className="h-4 w-4" />Create poll</Button>
            </form>
          </CardContent>
        </Card>}

        <Card className={canManageEngagement ? "" : "xl:col-span-3"}>
          <CardHeader><CardTitle className="text-base">People Moments</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {[...(moments.data?.birthdays || []).map((item: any) => ({ ...item, type: "Birthday" })), ...(moments.data?.anniversaries || []).map((item: any) => ({ ...item, type: "Anniversary" }))].slice(0, 6).map((item: any) => (
              <a key={`${item.type}-${item.employee_id}`} href={`/hrms/employees/${item.employee_id}`} className="flex justify-between rounded-lg border p-3 text-sm hover:bg-muted/50">
                <span>{item.name}</span><span className="text-muted-foreground">{item.type} â€¢ {formatDate(item.date)}</span>
              </a>
            ))}
            {!moments.data?.birthdays?.length && !moments.data?.anniversaries?.length && <p className="text-sm text-muted-foreground">No upcoming birthdays or anniversaries.</p>}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <Card>
          <CardHeader><CardTitle className="text-base">Live Poll</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <select className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={activeSurvey?.id || ""} onChange={(e) => setSelectedSurveyId(Number(e.target.value))}>
              {surveys.data?.map((item: any) => <option key={item.id} value={item.id}>{item.title}</option>)}
            </select>
            <div className="grid gap-2">
              {options.map((option: string) => (
                <Button key={option} type="button" variant={selectedOption === option ? "default" : "outline"} onClick={() => setSelectedOption(option)}>{option}</Button>
              ))}
            </div>
            <Button disabled={!activeSurvey || !selectedOption || vote.isPending} onClick={() => vote.mutate()}>Submit vote</Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-base">Poll Results</CardTitle></CardHeader>
          <CardContent className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={results.data?.results || []}>
                <XAxis dataKey="option" />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="count" fill="#2563eb" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-[0.85fr_1.15fr]">
        <Card>
          <CardHeader><CardTitle className="text-base">Team Shoutout</CardTitle></CardHeader>
          <CardContent>
            <form className="space-y-3" onSubmit={(e: FormEvent) => { e.preventDefault(); createRecognition.mutate(); }}>
              <select className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={recognition.to_employee_id} onChange={(e) => setRecognition({ ...recognition, to_employee_id: e.target.value })} required>
                <option value="">Select employee</option>
                {employees.data?.map((item: any) => <option key={item.id} value={item.id}>{item.first_name} {item.last_name} ({item.employee_id})</option>)}
              </select>
              <Input placeholder="Recognition title" value={recognition.title} onChange={(e) => setRecognition({ ...recognition, title: e.target.value })} required />
              <Input placeholder="Message" value={recognition.message} onChange={(e) => setRecognition({ ...recognition, message: e.target.value })} />
              <Button type="submit" disabled={createRecognition.isPending}><Trophy className="h-4 w-4" />Post shoutout</Button>
            </form>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-base">Recognition Wall</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {recognitions.data?.map((item: any) => (
              <div key={item.id} className="rounded-lg border p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-medium">{item.title}</p>
                    <p className="text-sm text-muted-foreground">{item.from_employee_name} recognized {item.to_employee_name}</p>
                  </div>
                  <Badge variant="secondary">{item.badge || "Shoutout"}</Badge>
                </div>
                {item.message && <p className="mt-2 text-sm">{item.message}</p>}
                <div className="mt-3 flex flex-wrap gap-2">
                  {["clap", "star", "heart"].map((emoji) => (
                    <Button key={emoji} variant="outline" size="sm" onClick={() => engagementApi.reactToRecognition(item.id, { emoji }).then(() => qc.invalidateQueries({ queryKey: ["recognition-wall"] }))}>
                      <Smile className="h-4 w-4" />{emoji} {item.reactions?.[emoji] || 0}
                    </Button>
                  ))}
                </div>
              </div>
            ))}
            {!recognitions.data?.length && <p className="rounded-lg border p-4 text-sm text-muted-foreground">No public recognitions yet.</p>}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
