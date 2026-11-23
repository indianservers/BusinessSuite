using System.Data;
using System.Text.Json;
using Npgsql;

namespace Business_Suite;

internal sealed partial class EmployeeAdministrationRepository
{
    internal static bool IsDeparted(string? status) => status is "Terminated" or "Exited" or "Resigned" or "Retired" or "Absconding";

    internal async Task<DataTable> ListLifecycleAsync(int employee, CancellationToken cancellation)
    {
        using var connection = new NpgsqlConnection(settings.ConnectionString);
        await connection.OpenAsync(cancellation);
        using var transaction = connection.BeginTransaction(IsolationLevel.RepeatableRead);
        await AuthorizeAsync(connection, transaction, false, cancellation);
        using var query = new NpgsqlCommand(@"
            WITH scoped AS (SELECT e.id " + ScopedEmployees + @" AND e.id = @employee)
            SELECT l.event_type, l.event_date::timestamp AS event_date, l.from_status, l.to_status,
                   l.reason
            FROM scoped JOIN public.employee_lifecycle_events l ON l.employee_id = scoped.id
            WHERE EXISTS (SELECT 1 FROM public.suite_branch_ownership o
                WHERE o.resource_table = 'employee_lifecycle_events' AND o.resource_key = l.id::text
                  AND o.company_id = @company AND o.branch_id = @branch)
            ORDER BY l.event_date DESC, l.id DESC LIMIT 100", connection, transaction);
        SetScope(query);
        query.Parameters.AddWithValue("employee", employee);
        return await ReadTableAsync(query, cancellation);
    }

    internal async Task ChangeEmploymentAsync(int employee, string revision, bool reactivate, string reason,
        CancellationToken cancellation)
    {
        reason = reason.Trim();
        if (reason.Length is < 3 or > 1000)
            throw new InvalidOperationException("Enter a reason of 3 to 1,000 characters.");

        using var connection = new NpgsqlConnection(settings.ConnectionString);
        await connection.OpenAsync(cancellation);
        using var transaction = connection.BeginTransaction();
        var actor = await AuthorizeAsync(connection, transaction, true, cancellation);
        await DesktopModuleAccess.RequireAsync(connection, transaction, settings.OrganizationId,
            settings.BranchId!.Value, actor, "hrms", "view", "employee_view");

        var (previous, linkedUser, businessDate, loginRevision) =
            await LockEmploymentAsync(connection, transaction, employee, revision, cancellation);

        if (reactivate != IsDeparted(previous))
            throw new InvalidOperationException(reactivate ? "Employment is already active." : "Employment has already ended.");
        actor = await AuthorizeAsync(connection, transaction, true, cancellation);
        bool? priorLoginActive = null;
        if (linkedUser.HasValue)
        {
            priorLoginActive = await LockLinkedLoginAsync(connection, transaction, linkedUser.Value, loginRevision,
                actor, cancellation);
            if (!reactivate)
                await WriteLoginStateAsync(connection, transaction, linkedUser.Value, actor.Id, false, "ACCOUNT_TERMINATE", reason, cancellation);
        }
        string newStatus = reactivate ? "Active" : "Terminated";
        using var change = new NpgsqlCommand(@"
            WITH employee AS (
                UPDATE public.employees SET status = @new_status,
                    date_of_exit = CASE WHEN @reactivate THEN NULL ELSE @today END, updated_at = clock_timestamp()
                WHERE id = @employee RETURNING id
            )
            INSERT INTO public.employee_lifecycle_events(employee_id, event_type, event_date, effective_from,
                from_status, to_status, reason, created_by)
            SELECT id, @event, @today, @today, @previous, @new_status, @reason, @actor FROM employee
            RETURNING id", connection, transaction);
        change.Parameters.AddWithValue("employee", employee);
        change.Parameters.AddWithValue("reactivate", reactivate);
        change.Parameters.AddWithValue("today", NpgsqlTypes.NpgsqlDbType.Date, businessDate);
        change.Parameters.AddWithValue("event", reactivate ? "Employment reactivated" : "Termination");
        AddText(change, "previous", previous);
        change.Parameters.AddWithValue("new_status", newStatus);
        change.Parameters.AddWithValue("reason", reason);
        change.Parameters.AddWithValue("actor", actor.Id);
        var eventId = (int)(await change.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(connection, transaction, "employee_lifecycle_events", eventId, cancellation);

        using var audit = new NpgsqlCommand(@"
            INSERT INTO public.audit_logs (organization_id, user_id, actor_email, actor_authenticated,
                method, endpoint, status_code, entity_type, entity_id, action, description,
                old_values, new_values, module)
            SELECT @company, id, left(email, 100), true, 'POST', @endpoint, 200, 'employee', @employee,
                @action, @reason, @before, @after, 'employees'
            FROM public.users WHERE id = @actor RETURNING id", connection, transaction);
        SetScope(audit);
        audit.Parameters.AddWithValue("actor", actor.Id);
        audit.Parameters.AddWithValue("employee", employee);
        audit.Parameters.AddWithValue("endpoint", $"desktop/employees/workbench/people/{employee}/actions");
        audit.Parameters.AddWithValue("action", reactivate ? "REACTIVATE_EMPLOYMENT" : "TERMINATE_EMPLOYMENT");
        audit.Parameters.AddWithValue("reason", reason);
        audit.Parameters.AddWithValue("before", JsonSerializer.Serialize(new { employment = previous, login_active = priorLoginActive }));
        audit.Parameters.AddWithValue("after", JsonSerializer.Serialize(new {
            employment = newStatus, login_active = reactivate || !linkedUser.HasValue ? priorLoginActive : false
        }));
        var auditId = (int)(await audit.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(connection, transaction, "audit_logs", auditId, cancellation);
        await transaction.CommitAsync(cancellation);
    }

    internal async Task ChangeLoginAccessAsync(int employee, string revision, bool activate, string reason,
        CancellationToken cancellation)
    {
        reason = reason.Trim();
        if (reason.Length is < 3 or > 1000)
            throw new InvalidOperationException("Enter a reason of 3 to 1,000 characters.");

        using var connection = new NpgsqlConnection(settings.ConnectionString);
        await connection.OpenAsync(cancellation);
        using var transaction = connection.BeginTransaction();
        var actor = await AuthorizeAsync(connection, transaction, true, cancellation);
        await DesktopModuleAccess.RequireAsync(connection, transaction, settings.OrganizationId,
            settings.BranchId!.Value, actor, "hrms", "view", "employee_view");
        var (employment, linkedUser, _, loginRevision) =
            await LockEmploymentAsync(connection, transaction, employee, revision, cancellation);
        if (!linkedUser.HasValue)
            throw new InvalidOperationException("This employee has no linked login.");
        if (activate && IsDeparted(employment))
            throw new InvalidOperationException("Reactivate employment before restoring login access.");

        actor = await AuthorizeAsync(connection, transaction, true, cancellation);
        bool wasActive = await LockLinkedLoginAsync(connection, transaction, linkedUser.Value, loginRevision,
            actor, cancellation);
        if (wasActive == activate)
            throw new InvalidOperationException(activate ? "Login access is already active." : "Login access is already disabled.");
        if (activate && !actor.IsSuperuser)
        {
            using var latest = new NpgsqlCommand(@"
                SELECT organization_id FROM public.audit_logs WHERE entity_type = 'user' AND entity_id = @user
                    AND action IN ('ACCOUNT_ACTIVATE', 'ACCOUNT_SUSPEND', 'ACCOUNT_TERMINATE')
                ORDER BY id DESC LIMIT 1", connection, transaction);
            latest.Parameters.AddWithValue("user", linkedUser.Value);
            if (!Equals(await latest.ExecuteScalarAsync(cancellation), settings.OrganizationId))
                throw new UnauthorizedAccessException("A Super Admin must reactivate a login disabled outside this HR scope.");
        }

        await WriteLoginStateAsync(connection, transaction, linkedUser.Value, actor.Id, activate,
            activate ? "ACCOUNT_ACTIVATE" : "ACCOUNT_SUSPEND", reason, cancellation);
        using var audit = new NpgsqlCommand(@"
            UPDATE public.employees SET updated_at = clock_timestamp() WHERE id = @employee;
            INSERT INTO public.audit_logs (organization_id, user_id, actor_email, actor_authenticated,
                method, endpoint, status_code, entity_type, entity_id, action, description,
                old_values, new_values, module)
            SELECT @company, id, left(email, 100), true, 'POST', @endpoint, 200, 'employee', @employee,
                @action, @reason, @before, @after, 'employees'
            FROM public.users WHERE id = @actor RETURNING id", connection, transaction);
        SetScope(audit);
        audit.Parameters.AddWithValue("actor", actor.Id);
        audit.Parameters.AddWithValue("employee", employee);
        audit.Parameters.AddWithValue("endpoint", $"desktop/employees/workbench/people/{employee}/actions");
        audit.Parameters.AddWithValue("action", activate ? "REACTIVATE_ACCESS" : "SUSPEND_ACCESS");
        audit.Parameters.AddWithValue("reason", reason);
        audit.Parameters.AddWithValue("before", JsonSerializer.Serialize(new { employment, login_active = wasActive }));
        audit.Parameters.AddWithValue("after", JsonSerializer.Serialize(new { employment, login_active = activate }));
        var id = (int)(await audit.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(connection, transaction, "audit_logs", id, cancellation);
        await transaction.CommitAsync(cancellation);
    }

    private async Task<(string? Status, int? Login, DateTime BusinessDate, string LoginRevision)> LockEmploymentAsync(
        NpgsqlConnection connection, NpgsqlTransaction transaction, int employee, string revision, CancellationToken cancellation)
    {
        var tokens = revision.Split(':');
        if (tokens.Length != 2)
            throw new InvalidOperationException("Refresh the employee record before applying this action.");
        using var query = new NpgsqlCommand(@"
            SELECT e.status, e.user_id,
                (clock_timestamp() AT TIME ZONE coalesce(nullif(
                    (SELECT c.default_timezone FROM public.companies c WHERE c.id = @company), ''),
                    'Asia/Kolkata'))::date::timestamp" + ScopedEmployees + @"
            AND e.id = @employee AND e.xmin::text = @revision FOR UPDATE OF e", connection, transaction);
        SetScope(query);
        query.Parameters.AddWithValue("employee", employee);
        query.Parameters.AddWithValue("revision", tokens[0]);
        using var row = await query.ExecuteReaderAsync(cancellation);
        if (!await row.ReadAsync(cancellation))
            throw new InvalidOperationException("The employee changed or is unavailable. Refresh before applying this action.");
        return (row.IsDBNull(0) ? null : row.GetString(0), row.IsDBNull(1) ? (int?)null : row.GetInt32(1),
            row.GetDateTime(2), tokens[1]);
    }

    private async Task<bool> LockLinkedLoginAsync(NpgsqlConnection connection, NpgsqlTransaction transaction,
        int user, string revision, DesktopActor actor, CancellationToken cancellation)
    {
        using (var lockedUser = new NpgsqlCommand(
            "SELECT id FROM public.users WHERE id = @user AND xmin::text = @revision FOR UPDATE",
            connection, transaction))
        {
            lockedUser.Parameters.AddWithValue("user", user);
            lockedUser.Parameters.AddWithValue("revision", revision);
            if (await lockedUser.ExecuteScalarAsync(cancellation) is not int)
                throw new InvalidOperationException("The linked login changed. Refresh before applying this action.");
        }

        using (var scopeRows = new NpgsqlCommand(@"
            SELECT id FROM public.suite_access_memberships WHERE user_id = @user
            ORDER BY id FOR SHARE", connection, transaction))
        {
            scopeRows.Parameters.AddWithValue("user", user);
            await scopeRows.ExecuteNonQueryAsync(cancellation);
        }

        using var query = new NpgsqlCommand(@"
            SELECT coalesce(u.is_active, false),
                   u.id = @actor OR coalesce(u.is_superuser, false)
                   OR coalesce(lower(replace(r.name, ' ', '_')) IN ('admin','super_admin'), false)
                   OR EXISTS (SELECT 1 FROM public.suite_access_memberships m
                              WHERE m.user_id = u.id AND m.active AND m.is_admin) AS protected_login,
                   EXISTS (
                       SELECT 1 FROM (
                           SELECT c.organization_id AS company FROM public.common_people c WHERE c.user_id = u.id
                           UNION SELECT b.company_id FROM public.employees e JOIN public.branches b ON b.id = e.branch_id
                               WHERE e.user_id = u.id
                           UNION SELECT m.company_id FROM public.suite_access_memberships m WHERE m.user_id = u.id AND m.active
                       ) companies
                       WHERE companies.company <> @company AND NOT EXISTS (
                           SELECT 1 FROM public.suite_access_memberships m
                           WHERE m.user_id = u.id AND m.company_id = companies.company AND NOT m.active)
                   ) AS spans_companies
            FROM public.users u LEFT JOIN public.roles r ON r.id = u.role_id
            WHERE u.id = @user", connection, transaction);
        SetScope(query);
        query.Parameters.AddWithValue("user", user);
        query.Parameters.AddWithValue("actor", actor.Id);
        using var row = await query.ExecuteReaderAsync(cancellation);
        if (!await row.ReadAsync(cancellation))
            throw new InvalidOperationException("The linked login changed. Refresh before applying this action.");
        if (row.GetBoolean(1) || row.GetBoolean(2))
            throw new UnauthorizedAccessException("This protected or multi-company login requires the administrator account workflow.");
        return row.GetBoolean(0);
    }

    private async Task WriteLoginStateAsync(NpgsqlConnection connection, NpgsqlTransaction transaction,
        int user, int actor, bool activate, string action, string reason, CancellationToken cancellation)
    {
        using var revoke = new NpgsqlCommand(@"
            UPDATE public.users SET is_active = @activate, updated_at = clock_timestamp() WHERE id = @user;
            UPDATE public.user_sessions SET status = 'revoked' WHERE NOT @activate AND user_id = @user AND status NOT IN ('revoked','Revoked');
            INSERT INTO public.audit_logs (organization_id, user_id, actor_email, actor_authenticated, method,
                endpoint, status_code, entity_type, entity_id, action, description, module)
            SELECT @company, u.id, left(u.email, 100), true, 'POST', 'desktop/employees/workbench/actions', 200,
                'user', @user, @action, @reason, 'employees'
            FROM public.users u WHERE u.id = @actor RETURNING id", connection, transaction);
        SetScope(revoke);
        revoke.Parameters.AddWithValue("user", user);
        revoke.Parameters.AddWithValue("activate", activate);
        revoke.Parameters.AddWithValue("action", action);
        revoke.Parameters.AddWithValue("actor", actor);
        revoke.Parameters.AddWithValue("reason", reason);
        var id = (int)(await revoke.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(connection, transaction, "audit_logs", id, cancellation);
    }
}

