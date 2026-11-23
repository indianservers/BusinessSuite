using System.Data;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record PmsBaselineOption(string Id, string Name, string CapturedAt)
{
    public string Label => Id.Length == 0 ? Name : $"{Name} · {CapturedAt}";
}
internal sealed record PmsBaselineView(PmsBaselineOption[] Options, PmsBaselineOption? Selected,
    DataTable Variance, int RemovedCount, string Revision, bool CanCapture, bool CanExport);

internal sealed partial class PmsProjectRepository
{
    private sealed record BaselineState(int? Workspace, bool Archived, bool Manage, int? Row, JsonObject Document,
        JsonArray Baselines, DataTable Tasks, DataTable Dependencies, string Revision);

    internal async Task<PmsBaselineView> ReadBaselinesAsync(int project, string? baselineId, CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await GetWorkspaceActorAsync(db, tx, false, cancellation);
        var state = await ReadBaselineStateAsync(db, tx, actor, project, false, cancellation);
        var options = state.Baselines.Select(item => new PmsBaselineOption(
            item!["id"]!.GetValue<string>(), item["name"]!.GetValue<string>(), item["created_at"]!.GetValue<string>())).ToArray();
        int selected = baselineId is null ? options.Length - 1 : Array.FindIndex(options, item => item.Id == baselineId);
        if (baselineId is not null && selected < 0)
            throw new InvalidOperationException("The baseline was not found in this project.");
        var snapshot = selected >= 0 ? ((JsonArray)state.Baselines[selected]!["tasks"]!).ToDictionary(
            row => row!["id"]!.GetValue<int>(), row => ReadBaselineDate(row!["due_date"])) : new();
        var rows = state.Tasks;
        rows.Columns.Add("baseline_due_date", typeof(DateTime));
        rows.Columns.Add("due_variance_days", typeof(int));
        rows.Columns.Add("in_baseline", typeof(bool));
        var active = new HashSet<int>();
        foreach (DataRow row in rows.Rows)
        {
            int id = row.Field<int>("id");
            active.Add(id);
            var inBaseline = snapshot.TryGetValue(id, out var oldDue);
            row["in_baseline"] = inBaseline;
            row["baseline_due_date"] = (object?)oldDue ?? DBNull.Value;
            if (oldDue.HasValue && row.Field<DateTime?>("due_date") is DateTime current)
                row["due_variance_days"] = (current.Date - oldDue.Value.Date).Days;
        }
        return new(options, selected >= 0 ? options[selected] : null, rows,
            snapshot.Keys.Count(id => !active.Contains(id)), state.Revision,
            state.Workspace.HasValue && !state.Archived && state.Manage && actor.ModuleCanEdit && options.Length < 20,
            actor.ModuleCanExport && selected >= 0);
    }

    internal async Task<string> CaptureBaselineAsync(int project, string name, string revision, CancellationToken cancellation)
    {
        name = name.Trim();
        if (name.Length is < 1 or > 100 || name.Any(char.IsControl))
            throw new InvalidOperationException("Enter a baseline name of 1 to 100 characters.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await GetWorkspaceActorAsync(db, tx, true, cancellation);
        var state = await ReadBaselineStateAsync(db, tx, actor, project, true, cancellation);
        if (state.Workspace is not int workspace)
            throw new InvalidOperationException("Move this project into a workspace before capturing a schedule baseline.");
        if (state.Archived)
            throw new InvalidOperationException("Archived projects cannot receive new baselines.");
        if (state.Revision != revision)
            throw new InvalidOperationException("The schedule changed. Refresh before capturing a baseline.");
        if (state.Baselines.Count >= 20)
            throw new InvalidOperationException("This project already has 20 retained baselines.");

        string id = Guid.NewGuid().ToString();
        state.Baselines.Add(JsonSerializer.SerializeToNode(new
        {
            id,
            name,
            created_at = DateTimeOffset.UtcNow.ToString("O", CultureInfo.InvariantCulture),
            author_id = actor.UserId,
            tasks = state.Tasks.Rows.Cast<DataRow>().Select(row => new
            {
                id = row.Field<int>("id"),
                start_date = ScheduleDate(row.Field<DateTime?>("start_date")),
                due_date = ScheduleDate(row.Field<DateTime?>("due_date"))
            }).ToArray()
        }));
        using var write = new NpgsqlCommand(state.Row.HasValue
            ? "UPDATE public.pms_workspace_entries SET body=@body WHERE id=@entry RETURNING id"
            : @"INSERT INTO public.pms_workspace_entries(workspace_id,author_id,kind,body)
                VALUES(@workspace,@actor,@kind,@body) RETURNING id", db, tx);
        write.Parameters.AddWithValue("body", state.Document.ToJsonString());
        write.Parameters.AddWithValue("workspace", workspace);
        write.Parameters.AddWithValue("actor", actor.UserId);
        write.Parameters.AddWithValue("kind", BaselineEntryKind(project));
        write.Parameters.Add("entry", NpgsqlDbType.Integer).Value = (object?)state.Row ?? DBNull.Value;
        int savedEntry = (int)(await write.ExecuteScalarAsync(cancellation))!;
        if (!state.Row.HasValue)
            await RecordOwnershipAsync(db, tx, "pms_workspace_entries", savedEntry, cancellation);
        await RecordActivityAsync(db, tx, project, "schedule.baseline", $"Captured schedule baseline: {name}",
            JsonSerializer.Serialize(new { baseline_id = id, task_count = state.Tasks.Rows.Count }), cancellation);
        await tx.CommitAsync(cancellation);
        return id;
    }

    private async Task<BaselineState> ReadBaselineStateAsync(NpgsqlConnection db, NpgsqlTransaction tx, PmsActor actor,
        int project, bool write, CancellationToken cancellation)
    {
        int? workspace;
        bool archived;
        bool manage;
        string projectRevision;
        using (var scoped = new NpgsqlCommand("SELECT p.workspace_id,coalesce(p.is_archived,false),coalesce((" + TaskEditAccess +
            "),false),p.xmin::text" + ProjectJoins + " WHERE " + ProjectAccess + " AND p.id=@project AND p.deleted_at IS NULL"
            + (write ? " FOR UPDATE OF p" : ""), db, tx))
        {
            SetActor(scoped, actor);
            scoped.Parameters.AddWithValue("project", project);
            using var result = await scoped.ExecuteReaderAsync(cancellation);
            if (!await result.ReadAsync(cancellation))
                throw new UnauthorizedAccessException("The project is unavailable.");
            workspace = result.IsDBNull(0) ? (int?)null : result.GetInt32(0);
            archived = result.GetBoolean(1);
            manage = result.GetBoolean(2);
            projectRevision = result.GetString(3);
        }
        if (write && (!manage || !actor.ModuleCanEdit))
            throw new UnauthorizedAccessException("Task-management authority is required to capture a schedule baseline.");

        int? entry = null;
        string? body = null;
        if (workspace.HasValue)
        {
            using var state = new NpgsqlCommand(@"
                SELECT e.id,e.body,(@branch IS NULL OR EXISTS(SELECT 1 FROM public.suite_branch_ownership o
                   WHERE o.resource_table='pms_workspace_entries' AND o.resource_key=e.id::text
                       AND o.company_id=@organization AND o.branch_id=@branch)) AS scoped
                FROM public.pms_workspace_entries e WHERE e.workspace_id=@workspace AND e.kind=@kind
                ORDER BY e.id LIMIT 2" + (write ? " FOR UPDATE OF e" : ""), db, tx);
            SetBranch(state);
            state.Parameters.AddWithValue("workspace", workspace.Value);
            state.Parameters.AddWithValue("kind", BaselineEntryKind(project));
            using var result = await state.ExecuteReaderAsync(cancellation);
            if (await result.ReadAsync(cancellation))
            {
                if (!result.GetBoolean(2))
                    throw new UnauthorizedAccessException("The existing baseline state is outside this branch.");
                entry = result.GetInt32(0);
                body = result.GetString(1);
                if (await result.ReadAsync(cancellation))
                    throw new InvalidOperationException("Multiple schedule state records exist for this project.");
            }
        }
        var document = JsonNode.Parse(body ?? @"{""calendar"":{""weekdays"":[0,1,2,3,4],""holidays"":[]},""baselines"":[]}") as JsonObject;
        if (document?["baselines"] is not JsonArray snapshots || document["calendar"] is not JsonObject)
            throw new InvalidOperationException("The saved schedule state cannot be read.");

        using var tasks = new NpgsqlCommand(@"SELECT t.id,t.task_key,t.title,t.status,t.start_date::timestamp,t.due_date::timestamp,
            t.xmin::text AS revision,(" + TaskBranchScope + @") AS scoped
            FROM public.pms_tasks t WHERE t.project_id=@project AND t.deleted_at IS NULL
            ORDER BY t.id LIMIT 1001" + (write ? " FOR SHARE OF t" : ""), db, tx);
        SetBranch(tasks);
        tasks.Parameters.AddWithValue("project", project);
        var rows = await ReadTableAsync(tasks, cancellation);
        if (rows.Rows.Count > 1000)
            throw new InvalidOperationException("Schedule baselines support up to 1,000 tasks per project.");
        if (rows.Rows.Cast<DataRow>().Any(row => !row.Field<bool>("scoped")))
            throw new UnauthorizedAccessException("The project's schedule contains tasks outside this branch.");
        int[] ids = rows.Rows.Cast<DataRow>().Select(item => item.Field<int>("id")).ToArray();
        using var edges = new NpgsqlCommand(@"
            SELECT d.id,d.task_id,d.depends_on_task_id,d.dependency_type,d.lag_days,d.xmin::text AS revision,
                (@branch IS NULL OR EXISTS(SELECT 1 FROM public.suite_branch_ownership o WHERE o.resource_table='pms_task_dependencies'
                    AND o.resource_key=d.id::text AND o.company_id=@organization AND o.branch_id=@branch)) AS scoped
            FROM public.pms_task_dependencies d
            WHERE d.task_id=ANY(@ids) OR d.depends_on_task_id=ANY(@ids) ORDER BY d.id", db, tx);
        SetBranch(edges);
        edges.Parameters.AddWithValue("ids", NpgsqlDbType.Array | NpgsqlDbType.Integer, ids);
        var dependencies = await ReadTableAsync(edges, cancellation);
        if (dependencies.Rows.Cast<DataRow>().Any(row => !row.Field<bool>("scoped")))
            throw new UnauthorizedAccessException("The project schedule contains a dependency outside this branch.");
        var active = new HashSet<int>(ids);
        if (dependencies.Rows.Cast<DataRow>().Any(row =>
            !active.Contains(row.Field<int>("task_id")) || !active.Contains(row.Field<int>("depends_on_task_id"))))
            throw new InvalidOperationException("Resolve dependencies outside this project's active task set before advanced planning.");

        string token = projectRevision + "|" + (body ?? "") + "|" +
            string.Join(",", rows.Rows.Cast<DataRow>().Select(item => $"{item["id"]}:{item["revision"]}")) + "|" +
            string.Join(",", dependencies.Rows.Cast<DataRow>().Select(item => $"{item["id"]}:{item["revision"]}"));
        using var sha = SHA256.Create();
        string revision = BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(token))).Replace("-", "");
        return new(workspace, archived, manage, entry, document, snapshots, rows, dependencies, revision);
    }

    private static string BaselineEntryKind(int project) => "sc" + project.ToString("x", CultureInfo.InvariantCulture);

    private static DateTime? ReadBaselineDate(JsonNode? date) => date is null ? (DateTime?)null :
        DateTime.ParseExact(date.GetValue<string>(), "yyyy-MM-dd", CultureInfo.InvariantCulture);
}
