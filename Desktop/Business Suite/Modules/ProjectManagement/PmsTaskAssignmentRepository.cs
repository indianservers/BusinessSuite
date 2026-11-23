using System.Data;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record PmsAssignmentList(string Revision, DataTable People);

internal sealed partial class PmsProjectRepository
{
    private const string AssignmentRevision = @"concat(t.xmin::text, ':',
        coalesce((SELECT max(a.id) FROM public.pms_activities a WHERE a.task_id=t.id
            AND a.action IN ('task.created','task.updated','task.assignment_selection','task.deleted',
                'task.restored','task.moved','task.reordered','sprint.changed')),0), ':',
        coalesce((SELECT md5(string_agg(concat(a.user_id,':',a.xmin::text), ',' ORDER BY a.user_id))
                   FROM public.pms_task_assignees a WHERE a.task_id=t.id),''))";

    private const string TaskAssignmentScope = ProjectJoins + @"
        JOIN public.pms_tasks t ON t.project_id = p.id
        WHERE " + ProjectAccess + " AND (" + TaskEditAccess + ") AND " + TaskBranchScope + @"
          AND p.deleted_at IS NULL AND t.deleted_at IS NULL AND t.id = @task";

    private async Task<DataTable> ReadAssignmentPeopleAsync(NpgsqlConnection connection, NpgsqlTransaction transaction,
        PmsActor actor, int task, int project, int? workspace, CancellationToken cancellation)
    {
        using var query = new NpgsqlCommand(@"
            WITH eligible AS (
                SELECT u.id, u.email
                FROM public.users u
                LEFT JOIN public.common_people person ON person.user_id = u.id
                LEFT JOIN public.employees employee ON employee.user_id = u.id AND employee.deleted_at IS NULL
                WHERE u.is_active AND (person.id IS NULL OR person.status = 'active')
                  AND (employee.id IS NULL OR employee.status NOT IN ('Terminated','Inactive','Suspended'))
                  AND (
                      u.id = @actor OR (
                         (@person_scope IN ('all','company','organization')
                         OR (@person_scope = 'branch' AND employee.branch_id = @employee_branch)
                         OR (@person_scope = 'department' AND employee.department_id = @department))
                         AND NOT EXISTS (SELECT 1 FROM public.suite_access_memberships m
                             WHERE m.user_id = u.id AND m.company_id = @organization AND NOT m.active)
                         AND (person.organization_id = @organization OR EXISTS (
                                 SELECT 1 FROM public.suite_access_memberships m
                                 WHERE m.user_id = u.id AND m.company_id = @organization AND m.active)
                             OR EXISTS (SELECT 1 FROM public.branches b
                                 WHERE b.id = employee.branch_id AND b.company_id = @organization))
                         AND (
                             (@workspace IS NOT NULL AND EXISTS (
                                 SELECT 1 FROM public.pms_workspace_members m
                                 WHERE m.workspace_id = @workspace AND m.user_id=u.id AND m.role IN ('Owner','Admin','Member')
                                   AND (@branch IS NULL OR EXISTS (SELECT 1 FROM public.suite_branch_ownership o
                                       WHERE o.resource_table = 'pms_workspace_members' AND o.resource_key = m.id::text
                                         AND o.company_id = @organization AND o.branch_id = @branch))))
                             OR (@workspace IS NULL AND EXISTS (
                                 SELECT 1 FROM public.pms_project_members m
                                 WHERE m.project_id = @project AND m.user_id = u.id AND m.role NOT IN ('Client','Client Viewer')
                                   AND (@branch IS NULL OR EXISTS (SELECT 1 FROM public.suite_branch_ownership o
                                       WHERE o.resource_table = 'pms_project_members' AND o.resource_key = m.id::text
                                         AND o.company_id = @organization AND o.branch_id = @branch))))
                             OR EXISTS (SELECT 1 FROM public.pms_projects p WHERE p.id = @project AND p.manager_user_id = u.id
                               AND (@branch IS NULL OR employee.branch_id = @branch OR EXISTS (
                                   SELECT 1 FROM public.suite_branch_grants b WHERE b.user_id = u.id
                                     AND b.company_id = @organization AND b.branch_id = @branch)))
                         )
                      )
                  )
            ), existing AS (
                SELECT a.user_id AS id, a.source_key IS NOT NULL AS protected FROM public.pms_task_assignees a WHERE a.task_id = @task
                UNION ALL SELECT t.assignee_user_id, false FROM public.pms_tasks t WHERE t.id=@task AND t.assignee_user_id IS NOT NULL
            ), assigned AS (SELECT id, bool_or(protected) AS protected FROM existing GROUP BY id)
            SELECT coalesce(e.id,a.id) AS id,
                   coalesce(e.email, CASE WHEN a.protected THEN 'Batch assignment' ELSE 'Unavailable collaborator' END) AS person,
                   a.id IS NOT NULL AS assigned, coalesce(a.protected, false) AS protected, e.id IS NOT NULL AS eligible
            FROM eligible e FULL JOIN assigned a ON a.id=e.id
            ORDER BY coalesce(e.email,''), coalesce(e.id,a.id)", connection, transaction);
        SetActor(query, actor);
        query.Parameters.AddWithValue("task", task);
        query.Parameters.AddWithValue("project", project);
        query.Parameters.AddWithValue("workspace", NpgsqlDbType.Integer, (object?)workspace ?? DBNull.Value);
        query.Parameters.AddWithValue("person_scope", actor.PersonScope);
        return await ReadTableAsync(query, cancellation);
    }

    internal async Task<PmsAssignmentList> LoadTaskAssignmentsAsync(int task, CancellationToken cancellation)
    {
        using var connection = new NpgsqlConnection(settings.ConnectionString);
        await connection.OpenAsync(cancellation);
        using var transaction = connection.BeginTransaction(IsolationLevel.RepeatableRead);
        var identity = await settings.RequireActorAsync(connection, transaction, cancellation);
        var actor = await ResolveActorAsync(settings, identity, connection, transaction, cancellation);
        RequireAssignmentEdit(actor);
        int project;
        int? workspace;
        string revision;
        using (var query = new NpgsqlCommand(
            "SELECT p.id, p.workspace_id, " + AssignmentRevision + TaskAssignmentScope, connection, transaction))
        {
            SetActor(query, actor);
            query.Parameters.AddWithValue("task", task);
            using var row = await query.ExecuteReaderAsync(cancellation);
            if (!await row.ReadAsync(cancellation))
                throw new UnauthorizedAccessException("This task is unavailable for assignment.");
            project = row.GetInt32(0);
            workspace = row.IsDBNull(1) ? null : row.GetInt32(1);
            revision = row.GetString(2);
        }
        var people = await ReadAssignmentPeopleAsync(connection, transaction, actor, task, project, workspace, cancellation);
        return new PmsAssignmentList(revision, people);
    }

    internal async Task SaveTaskAssignmentsAsync(int task, string revision, int[] assignees, string note, bool notify,
        CancellationToken cancellation)
    {
        if (assignees.Length > 100 || assignees.Any(id => id < 1) || assignees.Distinct().Count() != assignees.Length)
            throw new InvalidOperationException("Choose at most 100 unique assignees.");
        note = note.Trim();
        if (note.Length > 2000)
            throw new InvalidOperationException("Use 2,000 or fewer characters in the assignment note.");
        using var connection = new NpgsqlConnection(settings.ConnectionString);
        await connection.OpenAsync(cancellation);
        using var transaction = connection.BeginTransaction();
        var actor = await ResolveActorAsync(settings,
            await settings.VerifyWriteTargetAsync(connection, transaction, cancellation), connection, transaction, cancellation);
        RequireAssignmentEdit(actor);

        int project;
        int? workspace;
        using (var query = new NpgsqlCommand(
            "SELECT p.id, p.workspace_id" + TaskAssignmentScope + " FOR UPDATE OF p", connection, transaction))
        {
            SetActor(query, actor);
            query.Parameters.AddWithValue("task", task);
            using var row = await query.ExecuteReaderAsync(cancellation);
            if (!await row.ReadAsync(cancellation))
                throw new UnauthorizedAccessException("This task is unavailable for assignment.");
            project = row.GetInt32(0);
            workspace = row.IsDBNull(1) ? null : row.GetInt32(1);
        }

        if (workspace.HasValue)
        {
            using var lockWorkspace = new NpgsqlCommand(
                "SELECT id FROM public.pms_workspaces WHERE id=@workspace FOR UPDATE", connection, transaction);
            lockWorkspace.Parameters.AddWithValue("workspace", workspace.Value);
            await lockWorkspace.ExecuteScalarAsync(cancellation);
        }

        actor = await ResolveActorAsync(settings,
            await settings.VerifyWriteTargetAsync(connection, transaction, cancellation), connection, transaction, cancellation);
        RequireAssignmentEdit(actor);
        string before;
        string title;
        string key;
        using (var query = new NpgsqlCommand(
            "SELECT " + TaskSnapshot + ", t.title, t.task_key, " + AssignmentRevision + TaskAssignmentScope + " FOR UPDATE OF t",
            connection, transaction))
        {
            SetActor(query, actor);
            query.Parameters.AddWithValue("task", task);
            using var row = await query.ExecuteReaderAsync(cancellation);
            if (!await row.ReadAsync(cancellation) || row.GetString(3) != revision)
                throw new InvalidOperationException("The task or its assignment changed. Reopen Assign task to continue.");
            before = row.GetString(0);
            title = row.GetString(1);
            key = row.GetString(2);
        }

        var people = await ReadAssignmentPeopleAsync(connection, transaction, actor, task, project, workspace, cancellation);
        var chosen = new HashSet<int>(assignees);
        var eligible = new HashSet<int>();
        var notifyUsers = new List<int>();
        var old = new List<int>();
        foreach (DataRow person in people.Rows)
        {
            var id = person.Field<int>("id");
            if (person.Field<bool>("assigned"))
                old.Add(id);
            if (person.Field<bool>("protected") && !chosen.Contains(id))
                throw new InvalidOperationException("Batch-controlled work must be removed through Batch controls.");
            if (person.Field<bool>("protected") || person.Field<bool>("eligible"))
                eligible.Add(id);
            if (person.Field<bool>("eligible") && chosen.Contains(id) && id != actor.UserId)
                notifyUsers.Add(id);
        }
        if (!chosen.IsSubsetOf(eligible))
            throw new InvalidOperationException("Choose active people with access to this project.");

        using var change = new NpgsqlCommand(@"
            WITH removed AS (
                DELETE FROM public.pms_task_assignees WHERE task_id = @task AND source_key IS NULL
                    AND NOT(user_id = ANY(@assignees)) RETURNING task_id,user_id
            )
            DELETE FROM public.suite_branch_ownership o USING removed r
            WHERE o.resource_table='pms_task_assignees' AND o.company_id=@organization AND o.branch_id=@branch
                AND o.resource_key=concat(length(r.task_id::text),':',r.task_id,':',length(r.user_id::text),':',r.user_id);

            WITH added AS (
                INSERT INTO public.pms_task_assignees (task_id,user_id) SELECT @task, id FROM unnest(@assignees) id
                ON CONFLICT (task_id,user_id) DO NOTHING RETURNING task_id,user_id
            )
            INSERT INTO public.suite_branch_ownership(resource_table,resource_key,company_id,branch_id, source)
            SELECT 'pms_task_assignees',concat(length(task_id::text),':',task_id,':',length(user_id::text),':',user_id),
                @organization,@branch,'validated-write'
            FROM added WHERE @branch IS NOT NULL;

            UPDATE public.pms_tasks SET assignee_user_id =
                CASE WHEN assignee_user_id = ANY(@assignees) THEN assignee_user_id ELSE NULL END,
                updated_at = clock_timestamp() WHERE id = @task", connection, transaction);
        SetBranch(change);
        change.Parameters.AddWithValue("task", task);
        change.Parameters.AddWithValue("assignees", NpgsqlDbType.Array | NpgsqlDbType.Integer, assignees);
        await change.ExecuteNonQueryAsync(cancellation);

        using var choices = new NpgsqlCommand(@"
            SELECT coalesce((SELECT metadata_json FROM public.pms_activities
                WHERE task_id=@task AND action='task.assignment_selection' ORDER BY id DESC LIMIT 1),'{}')",
            connection, transaction);
        choices.Parameters.AddWithValue("task", task);
        using var priorSelection = JsonDocument.Parse((string)(await choices.ExecuteScalarAsync(cancellation))!);
        var nextSelection = priorSelection.RootElement.EnumerateObject().ToDictionary(entry => entry.Name, entry => (object)entry.Value);
        nextSelection["people"] = assignees.OrderBy(id => id).ToArray();
        nextSelection["resolved_ids"] = nextSelection["people"];
        await RecordTaskActivityAsync(connection, transaction, actor, project, task, task, "task.assignment_selection",
            $"Updated assignment selections for {key}", JsonSerializer.Serialize(nextSelection), cancellation);
        await RecordTaskActivityAsync(connection, transaction, actor, project, task, task, "assignee.changed",
            $"Changed assignees on {key}", JsonSerializer.Serialize(new { old_value = old, new_value = assignees, note }), cancellation);

        using var snapshot = new NpgsqlCommand(
            "SELECT " + TaskSnapshot + " FROM public.pms_tasks t WHERE t.id=@task", connection, transaction);
        snapshot.Parameters.AddWithValue("task", task);
        var after = (string)(await snapshot.ExecuteScalarAsync(cancellation))!;
        if (workspace.HasValue && before != after)
            await RecordTaskRecoveryAsync(connection, transaction, actor, workspace.Value, task, before, after, false, cancellation);

        if (notify && notifyUsers.Count > 0)
        {
            using var notifications = new NpgsqlCommand(@"
                WITH notices AS (
                    INSERT INTO public.notifications(company_id,user_id,title,message,module,event_type,related_entity_type,
                        related_entity_id,action_url,priority,channels,is_read)
                    SELECT @organization,id,'Task assignment updated',@message,'project_management','task.assigned',
                        'task',@task,@url,'normal','[""in_app""]'::json,false
                    FROM unnest(@assignees) id WHERE id <> @actor RETURNING id
                )
                INSERT INTO public.suite_branch_ownership(resource_table,resource_key,company_id,branch_id,source)
                SELECT 'notifications',id::text,@organization,@branch,'validated-write' FROM notices WHERE @branch IS NOT NULL",
                connection, transaction);
            SetBranch(notifications);
            notifications.Parameters.AddWithValue("actor", actor.UserId);
            notifications.Parameters.AddWithValue("task", task);
            notifications.Parameters.AddWithValue("message", note.Length == 0 ? title : $"{title} — {note}");
            notifications.Parameters.AddWithValue("url", $"/pms/tasks/{task}");
            notifications.Parameters.AddWithValue("assignees", NpgsqlDbType.Array | NpgsqlDbType.Integer, notifyUsers.ToArray());
            await notifications.ExecuteNonQueryAsync(cancellation);
        }
        await transaction.CommitAsync(cancellation);
    }

    private static void RequireAssignmentEdit(PmsActor actor)
    {
        if (!actor.ModuleCanEdit)
            throw new UnauthorizedAccessException("Your access policy does not allow editing task assignment.");
    }
}

