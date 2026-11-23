using System.Data;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record EmployeeExitView(DataTable Tasks, string? Status, DateTime? LastDay, DateTime Today,
    bool CanStart, bool CanComplete, int? Case, string? Revision, bool CanApprove, bool CanClose);
internal sealed partial class EmployeeAdministrationRepository
{
    private const string ExitOwnership = @"EXISTS(SELECT 1 FROM public.suite_branch_ownership o
        WHERE o.resource_table='exit_records' AND o.resource_key=x.id::text AND o.company_id=@company AND o.branch_id=@branch)";
    private const string ExitItemOwnership = @"EXISTS(SELECT 1 FROM public.suite_branch_ownership o
        WHERE o.resource_table='exit_checklist_items' AND o.resource_key=i.id::text AND o.company_id=@company AND o.branch_id=@branch)";

    internal async Task<EmployeeExitView> ReadExitAsync(int employee, CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await AuthorizeExitAsync(db, tx, false, cancellation);
        var current = await ReadExitEmployeeAsync(db, tx, employee, false, cancellation);
        var exit = await ReadExistingExitAsync(db, tx, employee, cancellation);
        bool manage = false;
        if (actor.CanWriteBranch)
        {
            try
            {
                var grant = await DesktopModuleAccess.RequireAsync(db, tx, settings.OrganizationId, settings.BranchId!.Value,
                    actor, "hrms", "edit", "exit_manage");
                manage = grant.Scope is "organization" or "branch";
            }
            catch (UnauthorizedAccessException) { }
        }

        using var taskList = new NpgsqlCommand(@"
            SELECT i.id,i.xmin::text AS revision,i.task_name,i.assigned_to_role,coalesce(i.is_completed,false) AS is_completed,
                i.completed_at,i.remarks
            FROM public.exit_checklist_items i JOIN public.exit_records x ON x.id=i.exit_record_id
            WHERE x.id=@exit AND x.employee_id=@employee AND " + ExitOwnership + " AND " + ExitItemOwnership + " ORDER BY i.id", db, tx);
        SetScope(taskList);
        taskList.Parameters.AddWithValue("exit", exit.Id ?? 0);
        taskList.Parameters.AddWithValue("employee", employee);
        bool canStart = manage && (exit.Id is null || exit.Rehired);
        bool canComplete = manage && exit.Id.HasValue && exit.Status is not ("Completed" or "Cancelled");
        return new(await ReadTableAsync(taskList, cancellation), exit.Status, exit.LastDay, current.Today, canStart, canComplete, exit.Id, exit.Revision, manage && exit.Status == "Initiated",
            manage && exit.Status == "In Progress");
    }

    internal async Task<int> StartExitAsync(int employee, DateTime lastDay, string type, string reason, CancellationToken cancellation)
    {
        if (type is not ("Resignation" or "Termination" or "Retirement"))
            throw new InvalidOperationException("Choose Resignation, Termination or Retirement.");
        reason = ValidateExitReason(reason);
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await AuthorizeExitAsync(db, tx, true, cancellation);
        var current = await ReadExitEmployeeAsync(db, tx, employee, true, cancellation);
        if (lastDay.Date < current.Joining.Date)
            throw new InvalidOperationException("Last working date cannot precede the joining date.");
        var existing = await ReadExistingExitAsync(db, tx, employee, cancellation);
        if (existing.Id.HasValue && !existing.Rehired)
            throw new InvalidOperationException("An exit case already exists for this employment period. Open its checklist.");

        using var create = new NpgsqlCommand(@"
            WITH exit_case AS (
                INSERT INTO public.exit_records(employee_id,exit_type,resignation_date,last_working_date,reason,status)
                VALUES(@employee,@type,@today,@last,@reason,'Initiated') RETURNING id
            ), tasks AS (
                INSERT INTO public.exit_checklist_items(exit_record_id,task_name,assigned_to_role,is_completed)
                SELECT x.id,list.title,list.role,false FROM exit_case x CROSS JOIN (VALUES
                    (1,'Transfer open tasks and project ownership','Manager'),
                    (2,'Revoke login access and active sessions','IT'),
                    (3,'Return company assets and confirm condition','IT'),
                    (4,'Complete exit documents and certificates','HR'),
                    (5,'Review final settlement and outstanding recoveries','Finance')) list(sequence,title,role)
                ORDER BY list.sequence RETURNING id
            ), owned AS (
                INSERT INTO public.suite_branch_ownership(resource_table,resource_key,company_id,branch_id,source)
                SELECT 'exit_records',id::text,@company,@branch,'validated-write' FROM exit_case
                UNION ALL SELECT 'exit_checklist_items',id::text,@company,@branch,'validated-write' FROM tasks
            ) SELECT id FROM exit_case", db, tx);
        SetScope(create);
        create.Parameters.AddWithValue("employee", employee);
        create.Parameters.AddWithValue("type", type);
        create.Parameters.AddWithValue("today", NpgsqlDbType.Date, current.Today);
        create.Parameters.AddWithValue("last", NpgsqlDbType.Date, lastDay.Date);
        create.Parameters.AddWithValue("reason", reason);
        int id = (int)(await create.ExecuteScalarAsync(cancellation))!;
        await RecordExitAuditAsync(db, tx, actor.Id, employee, "START_EXIT", reason, new { exit_id = id, last_working_date = lastDay.Date }, cancellation);
        await tx.CommitAsync(cancellation);
        return id;
    }

    internal async Task CompleteExitItemAsync(int employee, int item, string revision, string reason, CancellationToken cancellation)
    {
        reason = ValidateExitReason(reason);
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await AuthorizeExitAsync(db, tx, true, cancellation);
        var current = await ReadExitEmployeeAsync(db, tx, employee, true, cancellation);
        string title;
        using (var query = new NpgsqlCommand(@"
            SELECT i.task_name FROM public.exit_checklist_items i JOIN public.exit_records x ON x.id=i.exit_record_id
            WHERE i.id=@item AND i.xmin::text=@revision AND NOT coalesce(i.is_completed,false)
              AND x.employee_id=@employee AND x.status NOT IN ('Completed','Cancelled')
              AND " + ExitOwnership + " AND " + ExitItemOwnership + " FOR UPDATE OF i,x", db, tx))
        {
            SetScope(query);
            query.Parameters.AddWithValue("item", item);
            query.Parameters.AddWithValue("revision", revision);
            query.Parameters.AddWithValue("employee", employee);
            title = await query.ExecuteScalarAsync(cancellation) as string
                ?? throw new InvalidOperationException("The clearance item changed or is unavailable. Refresh before completing.");
        }
        if (title.IndexOf("access", StringComparison.OrdinalIgnoreCase) >= 0)
            await RequireExitLoginClearedAsync(db, tx, current.Login, cancellation);
        if (title.IndexOf("asset", StringComparison.OrdinalIgnoreCase) >= 0)
            await RequireExitAssetsClearedAsync(db, tx, employee, cancellation);
        using var update = new NpgsqlCommand(@"UPDATE public.exit_checklist_items SET is_completed=true,
            completed_at=clock_timestamp(),remarks=@reason WHERE id=@item", db, tx);
        update.Parameters.AddWithValue("reason", reason);
        update.Parameters.AddWithValue("item", item);
        await update.ExecuteNonQueryAsync(cancellation);
        await RecordExitAuditAsync(db, tx, actor.Id, employee, "EXIT_CHECKLIST_COMPLETE", reason, new { item_id = item, task = title }, cancellation);
        await tx.CommitAsync(cancellation);
    }

    internal async Task DecideExitAsync(int employee, int record, string revision, bool close, CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await AuthorizeExitAsync(db, tx, true, cancellation);
        var current = await ReadExitEmployeeAsync(db, tx, employee, true, cancellation);
        string? type;
        string reason;
        DateTime last;
        using (var query = new NpgsqlCommand(@"
            SELECT x.exit_type,x.reason,x.last_working_date::timestamp
            FROM public.exit_records x WHERE x.id=@record AND x.employee_id=@employee AND x.xmin::text=@revision
                AND x.status=@expected AND " + ExitOwnership + " FOR UPDATE OF x", db, tx))
        {
            SetScope(query);
            query.Parameters.AddWithValue("record", record);
            query.Parameters.AddWithValue("employee", employee);
            query.Parameters.AddWithValue("revision", revision);
            query.Parameters.AddWithValue("expected", close ? "In Progress" : "Initiated");
            using var row = await query.ExecuteReaderAsync(cancellation);
            if (!await row.ReadAsync(cancellation))
                throw new InvalidOperationException("The exit status changed or is unavailable. Refresh before deciding.");
            type = row.IsDBNull(0) ? null : row.GetString(0);
            reason = row.IsDBNull(1) ? "Exit clearance completed" : row.GetString(1);
            last = row.IsDBNull(2) ? current.Today : row.GetDateTime(2);
        }

        if (!close)
        {
            using var approve = new NpgsqlCommand(@"UPDATE public.exit_records SET status='In Progress',
                approved_by=@actor,approved_at=clock_timestamp(),updated_at=clock_timestamp() WHERE id=@record", db, tx);
            approve.Parameters.AddWithValue("record", record);
            approve.Parameters.AddWithValue("actor", actor.Id);
            await approve.ExecuteNonQueryAsync(cancellation);
            await RecordExitAuditAsync(db, tx, actor.Id, employee, "EXIT_APPROVED", "Exit approved", new { exit_id=record }, cancellation);
        }
        else
        {
            await RequireExitAssetsClearedAsync(db, tx, employee, cancellation);
            using var incomplete = new NpgsqlCommand(@"SELECT EXISTS(SELECT 1 FROM public.exit_checklist_items i
                WHERE i.exit_record_id=@record AND (NOT coalesce(i.is_completed,false) OR NOT (" + ExitItemOwnership + ")))", db, tx);
            SetScope(incomplete);
            incomplete.Parameters.AddWithValue("record", record);
            if (await incomplete.ExecuteScalarAsync(cancellation) is true)
                throw new InvalidOperationException("Complete every branch-owned exit checklist item before closing.");
            await RequireExitLoginClearedAsync(db, tx, current.Login, cancellation);
            if (last > current.Today)
                throw new InvalidOperationException("The last working date has not arrived.");
            string finalStatus = type switch
            {
                "Termination" => "Terminated", "Retirement" => "Retired", "Absconding" => "Absconding", _ => "Resigned"
            };
            using var complete = new NpgsqlCommand(@"
                UPDATE public.exit_records SET status='Completed',updated_at=clock_timestamp() WHERE id=@record;
                UPDATE public.employees SET status=@after,date_of_exit=@last,updated_at=clock_timestamp() WHERE id=@employee;
                INSERT INTO public.employee_lifecycle_events(employee_id,event_type,event_date,from_status,to_status,reason,created_by)
                VALUES(@employee,'Exit completed',@last,@before,@after,@reason,@actor) RETURNING id", db, tx);
            complete.Parameters.AddWithValue("record", record);
            complete.Parameters.AddWithValue("employee", employee);
            complete.Parameters.AddWithValue("actor", actor.Id);
            complete.Parameters.AddWithValue("last", NpgsqlDbType.Date, last);
            complete.Parameters.AddWithValue("after", finalStatus);
            complete.Parameters.AddWithValue("reason", reason);
            AddText(complete, "before", current.Status);
            int eventId = (int)(await complete.ExecuteScalarAsync(cancellation))!;
            await RecordOwnershipAsync(db, tx, "employee_lifecycle_events", eventId, cancellation);
            await RecordExitAuditAsync(db, tx, actor.Id, employee, "EXIT_COMPLETED", reason,
                new { exit_id=record, status=finalStatus, last_working_date=last }, cancellation);
        }
        await tx.CommitAsync(cancellation);
    }

    private static async Task RequireExitLoginClearedAsync(NpgsqlConnection db, NpgsqlTransaction tx, int? user,
        CancellationToken cancellation)
    {
        if (!user.HasValue)
            return;
        using var login = new NpgsqlCommand(@"SELECT u.is_active OR EXISTS(SELECT 1 FROM public.user_sessions s
            WHERE s.user_id=u.id AND lower(s.status)='active' AND (s.expires_at IS NULL OR s.expires_at>clock_timestamp()))
            FROM public.users u WHERE u.id=@user FOR SHARE OF u", db, tx);
        login.Parameters.AddWithValue("user", user.Value);
        if (await login.ExecuteScalarAsync(cancellation) is true)
            throw new InvalidOperationException("Disable the linked login and revoke active sessions before completing clearance.");
    }

    private async Task RequireExitAssetsClearedAsync(NpgsqlConnection db, NpgsqlTransaction tx, int employee,
        CancellationToken cancellation)
    {
        using var assets = new NpgsqlCommand(@"
            WITH policy AS (
                SELECT values_json::jsonb AS settings FROM public.suite_service_policies
                WHERE organization_id=@company AND scope_key='asset-lifecycle:'||@company LIMIT 1
            )
            SELECT EXISTS(SELECT 1 FROM public.asset_assignments a JOIN public.assets b ON b.id=a.asset_id
                WHERE a.employee_id=@employee AND b.organization_id=@company AND (
                    a.is_active OR a.inspection_status IN ('Pending','Awaiting Approval','Rejected')
                    OR a.recovery_status IN ('Pending','Approved') OR (
                        coalesce(a.return_details->>'exception_status','')<>'Approved' AND (
                            a.condition_at_return='Lost'
                            OR (coalesce((SELECT (settings->>'block_missing_clearance')::boolean FROM policy),true)
                                AND jsonb_typeof(a.return_details::jsonb->'missing_accessories')='array'
                                AND a.return_details::jsonb->'missing_accessories'<>'[]'::jsonb
                                AND NOT coalesce((a.return_details::jsonb #>> '{inspection,missing_resolved}')::boolean,false))
                            OR (coalesce((SELECT (settings->>'block_damaged_clearance')::boolean FROM policy),false)
                                AND a.condition_at_return IN ('Poor','Damaged') AND a.recovery_status NOT IN ('Settled','Rejected'))
                       )
                    )
                ))", db, tx);
        SetScope(assets);
        assets.Parameters.AddWithValue("employee", employee);
        if (await assets.ExecuteScalarAsync(cancellation) is true)
            throw new InvalidOperationException("Resolve outstanding asset returns, inspections, exceptions and recoveries before completing clearance.");
    }

    private async Task<DesktopActor> AuthorizeExitAsync(NpgsqlConnection db, NpgsqlTransaction tx, bool write, CancellationToken cancellation)
    {
        int branch = settings.BranchId ?? throw new InvalidOperationException("Choose a branch before opening employee exits.");
        var actor = write ? await settings.VerifyWriteTargetAsync(db, tx, cancellation) : await settings.RequireActorAsync(db, tx, cancellation);
        var grant = await DesktopModuleAccess.RequireAsync(db, tx, settings.OrganizationId, branch, actor, "hrms",
            write ? "edit" : "view", write ? "exit_manage" : "exit_view");
        if (grant.Scope is not ("organization" or "branch"))
            throw new UnauthorizedAccessException("Employee exit requires organization or branch access.");
        return actor;
    }

    private async Task<(DateTime Joining, DateTime Today, int? Login, string? Status)> ReadExitEmployeeAsync(NpgsqlConnection db,
        NpgsqlTransaction tx, int employee, bool write, CancellationToken cancellation)
    {
        using var query = new NpgsqlCommand(@"SELECT e.date_of_joining::timestamp,
            (clock_timestamp() AT TIME ZONE coalesce(nullif(
                (SELECT default_timezone FROM public.companies WHERE id=@company),''),'Asia/Kolkata'))::date::timestamp,e.user_id,e.status"
            + ScopedEmployees + " AND e.id=@employee" + (write ? " FOR UPDATE OF e" : ""), db, tx);
        SetScope(query);
        query.Parameters.AddWithValue("employee", employee);
        using var row = await query.ExecuteReaderAsync(cancellation);
        if (!await row.ReadAsync(cancellation))
            throw new InvalidOperationException("The employee is unavailable in this branch.");
        return (row.GetDateTime(0), row.GetDateTime(1), row.IsDBNull(2) ? (int?)null : row.GetInt32(2), row.IsDBNull(3) ? null : row.GetString(3));
    }

    private async Task<(int? Id, string? Status, DateTime? LastDay, bool Rehired, string? Revision)> ReadExistingExitAsync(
        NpgsqlConnection db, NpgsqlTransaction tx, int employee, CancellationToken cancellation, int? selectedExit = null)
    {
        using var query = new NpgsqlCommand(@"
            SELECT x.id,x.status,x.last_working_date::timestamp,(" + ExitOwnership + @"),
                coalesce(x.status IN ('Completed','Cancelled') AND EXISTS(
                    SELECT 1 FROM public.employee_lifecycle_events e JOIN public.suite_branch_ownership o
                      ON o.resource_table='employee_lifecycle_events' AND o.resource_key=e.id::text
                     AND o.company_id=@company AND o.branch_id=@branch
                    WHERE e.employee_id=@employee AND e.event_type='Employment reactivated' AND e.created_at>x.created_at),false),x.xmin::text
            FROM public.exit_records x WHERE x.employee_id=@employee AND (@selected IS NULL OR x.id=@selected)
            ORDER BY x.id DESC LIMIT 1", db, tx);
        SetScope(query);
        query.Parameters.AddWithValue("employee", employee);
        query.Parameters.AddWithValue("selected",NpgsqlDbType.Integer,(object?)selectedExit ?? DBNull.Value);
        using var row = await query.ExecuteReaderAsync(cancellation);
        if (!await row.ReadAsync(cancellation))
            return (null, null, null, false, null);
        if (!row.GetBoolean(3))
            throw new UnauthorizedAccessException("The employee has an exit case outside this branch.");
        return (row.GetInt32(0), row.IsDBNull(1) ? null : row.GetString(1),
            row.IsDBNull(2) ? (DateTime?)null : row.GetDateTime(2), row.GetBoolean(4), row.GetString(5));
    }

    private async Task RecordExitAuditAsync(NpgsqlConnection db, NpgsqlTransaction tx, int actor, int employee,
        string action, string reason, object metadata, CancellationToken cancellation)
    {
        using var audit = new NpgsqlCommand(@"
            INSERT INTO public.audit_logs(organization_id,user_id,actor_email,actor_authenticated,method,endpoint,status_code,
                entity_type,entity_id,action,description,module,new_values)
            SELECT @company,id,left(email,100),true,'POST','desktop/hrms/exit',200,'employee',@employee,
                @action,@reason,'employees',@metadata FROM public.users WHERE id=@actor RETURNING id", db, tx);
        SetScope(audit);
        audit.Parameters.AddWithValue("actor", actor);
        audit.Parameters.AddWithValue("employee", employee);
        audit.Parameters.AddWithValue("action", action);
        audit.Parameters.AddWithValue("reason", reason);
        audit.Parameters.AddWithValue("metadata", JsonSerializer.Serialize(metadata));
        int id = (int)(await audit.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(db, tx, "audit_logs", id, cancellation);
    }

    private static string ValidateExitReason(string value)
    {
        value = value.Trim();
        if (value.Length is < 3 or > 1000)
            throw new InvalidOperationException("Enter a reason of 3 to 1,000 characters.");
        return value;
    }
}
