using System.Data;
using System.Text.Json;
using Npgsql;

namespace Business_Suite;

internal sealed record EmployeeOnboardingView(DataTable Templates, DataTable Tasks, string? Progress, bool CanWrite);

internal sealed partial class EmployeeAdministrationRepository
{
    private const string OnboardingTemplateScope = @" t.is_active AND (t.organization_id=@company OR t.organization_id IS NULL)
        AND NOT EXISTS (SELECT 1 FROM public.suite_branch_ownership o WHERE o.resource_table='onboarding_templates'
            AND o.resource_key=t.id::text AND (o.company_id<>@company OR o.branch_id<>@branch))";
    private const string OnboardingScope = @" EXISTS (SELECT 1 FROM public.suite_branch_ownership o
        WHERE o.resource_table='employee_onboardings' AND o.resource_key=p.id::text
          AND o.company_id=@company AND o.branch_id=@branch)";
    private const string OnboardingTaskScope = @" EXISTS (SELECT 1 FROM public.suite_branch_ownership o
        WHERE o.resource_table='employee_onboarding_tasks' AND o.resource_key=t.id::text
          AND o.company_id=@company AND o.branch_id=@branch)";

    internal async Task<EmployeeOnboardingView> ReadOnboardingAsync(int employee, CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await AuthorizeAsync(db, tx, false, cancellation);
        await GetOnboardingEmployeeAsync(db, tx, employee, false, cancellation);
        using var masters = new NpgsqlCommand("SELECT t.id,t.name FROM public.onboarding_templates t WHERE " +
            OnboardingTemplateScope + " ORDER BY t.name,t.id", db, tx);
        SetScope(masters);
        var templates = await ReadTableAsync(masters, cancellation);

        using var latest = new NpgsqlCommand(@"
            SELECT p.id,concat(initcap(replace(coalesce(p.status,''),'_',' ')),' · ',
                coalesce(p.completion_percentage,0),'%') AS progress
            FROM public.employee_onboardings p WHERE p.employee_id=@employee AND " + OnboardingScope +
            " ORDER BY p.id DESC LIMIT 1", db, tx);
        SetScope(latest);
        latest.Parameters.AddWithValue("employee", employee);
        int? plan = null;
        string? progress = null;
        using (var data = await latest.ExecuteReaderAsync(cancellation))
            if (await data.ReadAsync(cancellation))
            {
                plan = data.GetInt32(0);
                progress = data.GetString(1);
            }

        using var list = new NpgsqlCommand(@"
            SELECT t.id,t.xmin::text AS revision,t.task_name,t.category,t.status,t.due_date::timestamp,
                t.completed_at,t.notes,coalesce(t.status IN ('pending','in_progress','overdue') AND p.status NOT IN ('completed','cancelled'),false) AS open
            FROM public.employee_onboarding_tasks t JOIN public.employee_onboardings p ON p.id=t.employee_onboarding_id
            WHERE p.id=@plan AND p.employee_id=@employee AND " + OnboardingScope +
            " AND " + OnboardingTaskScope + " ORDER BY t.due_date NULLS LAST,t.id", db, tx);
        SetScope(list);
        list.Parameters.AddWithValue("plan", plan ?? 0);
        list.Parameters.AddWithValue("employee", employee);
        return new(templates, await ReadTableAsync(list, cancellation), progress, actor.CanWriteBranch);
    }

    internal async Task<int> ApplyOnboardingTemplateAsync(int employee, int template, CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await AuthorizeAsync(db, tx, true, cancellation);
        DateTime joining = await GetOnboardingEmployeeAsync(db, tx, employee, true, cancellation);
        using var target = new NpgsqlCommand("SELECT t.name FROM public.onboarding_templates t WHERE " + OnboardingTemplateScope
            + " AND t.id=@template FOR SHARE OF t", db, tx);
        SetScope(target);
        target.Parameters.AddWithValue("template", template);
        if (await target.ExecuteScalarAsync(cancellation) is not string name)
            throw new InvalidOperationException("Choose an active onboarding template in this branch.");
        using var existing = new NpgsqlCommand(@"SELECT p.id,(" + OnboardingScope + @") FROM public.employee_onboardings p
            WHERE p.employee_id=@employee AND p.template_id=@template ORDER BY p.id LIMIT 1", db, tx);
        SetScope(existing);
        existing.Parameters.AddWithValue("employee", employee);
        existing.Parameters.AddWithValue("template", template);
        using (var row = await existing.ExecuteReaderAsync(cancellation))
            if (await row.ReadAsync(cancellation))
            {
                if (!row.GetBoolean(1))
                    throw new UnauthorizedAccessException("An onboarding plan already exists outside this branch.");
                return row.GetInt32(0);
            }
        int id = await CreateEmployeeOnboardingAsync(db, tx, employee, joining, "", actor.Id, cancellation, template)
            ?? throw new InvalidOperationException("The onboarding template is unavailable.");
        await RecordOnboardingAuditAsync(db, tx, actor.Id, employee, "ONBOARDING_TEMPLATE_APPLIED", name,
            JsonSerializer.Serialize(new { template_id = template }), cancellation);
        await tx.CommitAsync(cancellation);
        return id;
    }

    internal async Task CompleteOnboardingTaskAsync(int employee, int item, string revision, string reason,
        CancellationToken cancellation)
    {
        reason = reason.Trim();
        if (reason.Length is < 3 or > 1000)
            throw new InvalidOperationException("Enter a reason of 3 to 1,000 characters.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await AuthorizeAsync(db, tx, true, cancellation);
        await GetOnboardingEmployeeAsync(db, tx, employee, true, cancellation);
        using var update = new NpgsqlCommand(@"
            UPDATE public.employee_onboarding_tasks t SET status='completed',completed_at=clock_timestamp(),
                completed_by=@actor,notes=@reason FROM public.employee_onboardings p
            WHERE t.id=@item AND t.employee_onboarding_id=p.id AND p.employee_id=@employee AND t.xmin::text=@revision
              AND t.status IN ('pending','in_progress','overdue') AND p.status NOT IN ('completed','cancelled')
              AND " + OnboardingScope + " AND " + OnboardingTaskScope + " RETURNING p.id", db, tx);
        SetScope(update);
        update.Parameters.AddWithValue("item", item);
        update.Parameters.AddWithValue("employee", employee);
        update.Parameters.AddWithValue("actor", actor.Id);
        update.Parameters.AddWithValue("reason", reason);
        update.Parameters.AddWithValue("revision", revision);
        if (await update.ExecuteScalarAsync(cancellation) is not int plan)
            throw new InvalidOperationException("The onboarding item changed or is unavailable. Refresh before completing.");
        using var rollup = new NpgsqlCommand(@"
            WITH current AS (
                SELECT count(*) AS total,count(*) FILTER(WHERE t.status IN ('completed','skipped')) AS done,
                    bool_or(t.status NOT IN ('completed','skipped') AND t.due_date <
                        (clock_timestamp() AT TIME ZONE coalesce(nullif(
                          (SELECT default_timezone FROM public.companies WHERE id=@company),''),'Asia/Kolkata'))::date) AS overdue,
                    bool_or(t.status<>'pending') AS in_progress
                FROM public.employee_onboarding_tasks t WHERE t.employee_onboarding_id=@plan AND " + OnboardingTaskScope + @"
            ) UPDATE public.employee_onboardings p SET
                completion_percentage=round(100.0*current.done/nullif(current.total,0))::int,
                status=CASE WHEN current.total>0 AND current.done=current.total THEN 'completed'
                            WHEN current.overdue THEN 'overdue' WHEN current.in_progress THEN 'in_progress' ELSE 'not_started' END
                FROM current WHERE p.id=@plan", db, tx);
        SetScope(rollup);
        rollup.Parameters.AddWithValue("plan", plan);
        await rollup.ExecuteNonQueryAsync(cancellation);
        await RecordOnboardingAuditAsync(db, tx, actor.Id, employee, "JOINER_TASK_COMPLETE", reason,
            JsonSerializer.Serialize(new { item_id = item }), cancellation);
        await tx.CommitAsync(cancellation);
    }

    private async Task<DateTime> GetOnboardingEmployeeAsync(NpgsqlConnection db, NpgsqlTransaction tx, int employee, bool write,
        CancellationToken cancellation)
    {
        using var query = new NpgsqlCommand("SELECT e.date_of_joining::timestamp" + ScopedEmployees + " AND e.id=@employee" +
            (write ? " FOR UPDATE OF e" : ""), db, tx);
        SetScope(query);
        query.Parameters.AddWithValue("employee", employee);
        return await query.ExecuteScalarAsync(cancellation) is DateTime date ? date :
            throw new InvalidOperationException("The employee is unavailable in this branch.");
    }

    private async Task RecordOnboardingAuditAsync(NpgsqlConnection db, NpgsqlTransaction tx, int actor, int employee,
        string action, string reason, string metadata, CancellationToken cancellation)
    {
        using var audit = new NpgsqlCommand(@"
            INSERT INTO public.audit_logs(organization_id,user_id,actor_email,actor_authenticated,method,endpoint,status_code,
                 entity_type,entity_id,action,description,module,new_values)
            SELECT @company,id,left(email,100),true,'POST','desktop/hrms/onboarding',200,'employee',@employee,
                 @action,@reason,'employees',@metadata FROM public.users WHERE id=@actor RETURNING id", db, tx);
        SetScope(audit);
        audit.Parameters.AddWithValue("actor", actor);
        audit.Parameters.AddWithValue("employee", employee);
        audit.Parameters.AddWithValue("action", action);
        audit.Parameters.AddWithValue("reason", reason);
        audit.Parameters.AddWithValue("metadata", metadata);
        int id = (int)(await audit.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(db, tx, "audit_logs", id, cancellation);
    }
}
