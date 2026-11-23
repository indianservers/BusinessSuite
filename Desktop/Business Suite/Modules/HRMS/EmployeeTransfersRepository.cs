using System.Data;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record EmployeeTransferDraft(int? Department, int? Designation, DateTime EffectiveFrom, string Reason,
    bool ChangeManager = false, int? Manager = null, bool ChangeShift = false, int? Shift = null);
internal sealed record EmployeeTransferContext(DataTable Departments, DataTable Designations, DataTable Managers, DataTable Shifts, DataTable History,
    int? CurrentDepartment, int? CurrentDesignation, DateTime Today, bool CanWrite);
internal sealed record EmployeeTransferPreview(string Revision, bool Scheduled, string Before, string After);

internal sealed partial class EmployeeAdministrationRepository
{
    private const string TransferEventScope = @" (@branch IS NOT NULL AND EXISTS (
        SELECT 1 FROM public.suite_branch_ownership o WHERE o.resource_table='employee_lifecycle_events'
           AND o.resource_key=l.id::text AND o.company_id=@company AND o.branch_id=@branch))";
    private const string TransferDesignationScope = @" FROM public.designations g JOIN public.departments d ON d.id=g.department_id
        WHERE g.is_active AND d.is_active AND d.branch_id=@branch
            AND (g.organization_id IS NULL OR g.organization_id=@company)
            AND (d.organization_id IS NULL OR d.organization_id=@company)
            AND NOT EXISTS (SELECT 1 FROM public.suite_branch_ownership o WHERE
                ((o.resource_table='designations' AND o.resource_key=g.id::text)
                OR (o.resource_table='departments' AND o.resource_key=d.id::text))
                AND (o.company_id<>@company OR o.branch_id<>@branch))";

    private sealed record TransferEmployee(int? Department, int? Designation, int? Manager, int? Shift, string? Status,
        string Revision, DateTime Today, string DepartmentName, string DesignationName, string ManagerName, string ShiftName);

    internal async Task<EmployeeTransferContext> ReadTransfersAsync(int employee, CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await AuthorizeAsync(db, tx, false, cancellation);
        var current = await ReadTransferEmployeeAsync(db, tx, employee, false, cancellation);

        using var departments = new NpgsqlCommand("SELECT d.id,d.name" + CreateDepartmentScope + " ORDER BY d.name,d.id", db, tx);
        SetScope(departments);
        using var designations = new NpgsqlCommand("SELECT g.id,g.name,g.department_id" + TransferDesignationScope + " ORDER BY g.name,g.id", db, tx);
        SetScope(designations);
        using var managers = new NpgsqlCommand("SELECT e.id,concat_ws(' ',e.first_name,e.last_name) AS name" +
            ScopedEmployees + ManagerEligibility + " AND e.id<>@employee ORDER BY name,e.id", db, tx);
        SetScope(managers);
        managers.Parameters.AddWithValue("employee", employee);
        using var shifts = new NpgsqlCommand("SELECT s.id,s.name FROM public.shifts s WHERE s.is_active AND " +
            TransferShiftScope + " ORDER BY s.name,s.id", db, tx);
        SetScope(shifts);
        using var history = new NpgsqlCommand(@"
            SELECT l.id,l.xmin::text AS revision,l.event_type,l.effective_from::timestamp AS effective_from,l.reason,
                   l.to_department_id,l.to_designation_id,d.name AS department,g.name AS designation,l.remarks,
                   coalesce(nullif(concat_ws(' ',m.first_name,m.last_name),''),'Unassigned') AS manager,
                   coalesce(l.event_type='Scheduled transfer' AND l.effective_from<=@today,false) AS due
            FROM public.employee_lifecycle_events l
            LEFT JOIN public.departments d ON d.id=l.to_department_id AND d.branch_id=@branch
            LEFT JOIN public.designations g ON g.department_id=d.id AND g.id=l.to_designation_id
            LEFT JOIN public.employees m ON m.id=l.to_manager_id AND m.branch_id=@branch
            WHERE l.employee_id=@employee AND l.event_type IN ('Scheduled transfer','Transfer applied')
                AND " + TransferEventScope + " ORDER BY l.effective_from DESC,l.id DESC LIMIT 100", db, tx);
        SetScope(history);
        history.Parameters.AddWithValue("employee", employee);
        history.Parameters.AddWithValue("today", NpgsqlDbType.Date, current.Today);
        var departmentRows = await ReadTableAsync(departments, cancellation);
        var designationRows = await ReadTableAsync(designations, cancellation);
        var managerRows = await ReadTableAsync(managers, cancellation);
        var shiftRows = await ReadTableAsync(shifts, cancellation);
        var historyRows = await ReadTableAsync(history, cancellation);
        var shiftNames = shiftRows.Rows.Cast<DataRow>().ToDictionary(row => (int)row["id"], row => (string)row["name"]);
        historyRows.Columns.Add("shift", typeof(string));
        foreach (DataRow row in historyRows.Rows)
            row["shift"] = TransferShiftLabel(row["remarks"] as string, shiftNames);
        historyRows.Columns.Remove("remarks");
        return new(departmentRows, designationRows, managerRows, shiftRows, historyRows,
            current.Department, current.Designation, current.Today, actor.CanWriteBranch);
    }

    internal async Task<EmployeeTransferPreview> PreviewTransferAsync(int employee, EmployeeTransferDraft draft,
        CancellationToken cancellation)
    {
        draft = ValidateTransferDraft(draft);
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await AuthorizeTransferAsync(db, tx, false, cancellation);
        var current = await ReadTransferEmployeeAsync(db, tx, employee, false, cancellation);
        var destination = await CheckTransferDestinationAsync(db, tx, employee, current, draft, false, cancellation);
        return BuildTransferPreview(actor.Id, employee, current, draft, destination);
    }

    internal async Task<int> SaveTransferAsync(int employee, EmployeeTransferDraft draft, string revision, CancellationToken cancellation)
    {
        draft = ValidateTransferDraft(draft);
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await AuthorizeTransferAsync(db, tx, true, cancellation);
        var current = await ReadTransferEmployeeAsync(db, tx, employee, true, cancellation);
        var destination = await CheckTransferDestinationAsync(db, tx, employee, current, draft, true, cancellation);
        var preview = BuildTransferPreview(actor.Id, employee, current, draft, destination);
        if (revision != preview.Revision)
            throw new InvalidOperationException("The employee or transfer draft changed. Preview the transfer again.");

        var previous = TransferValues(current.Department, current.Designation, draft.ChangeManager, current.Manager, draft.ChangeShift, current.Shift);
        var changes = TransferValues(draft.Department, draft.Designation, draft.ChangeManager, draft.Manager, draft.ChangeShift, draft.Shift);
        using var request = new NpgsqlCommand(@"
            INSERT INTO public.employee_lifecycle_events(employee_id,event_type,event_date,effective_from,from_status,
                from_branch_id,to_branch_id,from_department_id,to_department_id,from_designation_id,to_designation_id,
                from_manager_id,to_manager_id,reason,remarks,created_by)
            VALUES(@employee,@type,@today,@effective,@status,@branch,@branch,@old_department,@department,
                @old_designation,@designation,@old_manager,@manager,@reason,@remarks,@actor) RETURNING id", db, tx);
        SetScope(request);
        request.Parameters.AddWithValue("employee", employee);
        request.Parameters.AddWithValue("type", preview.Scheduled ? "Scheduled transfer" : "Transfer applied");
        request.Parameters.AddWithValue("today", NpgsqlDbType.Date, current.Today);
        request.Parameters.AddWithValue("effective", NpgsqlDbType.Date, draft.EffectiveFrom);
        request.Parameters.AddWithValue("reason", draft.Reason);
        request.Parameters.AddWithValue("actor", actor.Id);
        request.Parameters.AddWithValue("remarks", JsonSerializer.Serialize(new
        {
            previous, changes, state = preview.Scheduled ? "scheduled" : "applied"
        }));
        AddText(request, "status", current.Status);
        AddTransferId(request, "old_department", current.Department);
        AddTransferId(request, "old_designation", current.Designation);
        AddTransferId(request, "department", draft.Department);
        AddTransferId(request, "designation", draft.Designation);
        AddTransferId(request, "old_manager", current.Manager);
        AddTransferId(request, "manager", draft.ChangeManager ? draft.Manager : current.Manager);
        int id = (int)(await request.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(db, tx, "employee_lifecycle_events", id, cancellation);
        if (!preview.Scheduled)
            await UpdateTransferEmployeeAsync(db, tx, actor.Id, employee, current, draft, cancellation);
        await AuditTransferAsync(db, tx, employee, actor.Id, preview.Scheduled ? "TRANSFER_SCHEDULED" : "TRANSFER_APPLIED",
            draft.Reason, previous, changes, cancellation);
        await tx.CommitAsync(cancellation);
        return id;
    }

    internal async Task ApplyDueTransferAsync(int employee, int entry, string revision, CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await AuthorizeTransferAsync(db, tx, true, cancellation);
        var current = await ReadTransferEmployeeAsync(db, tx, employee, true, cancellation);
        string text;
        string reason;
        DateTime due;
        using (var plan = new NpgsqlCommand(@"
            SELECT l.remarks,l.reason,l.effective_from::timestamp FROM public.employee_lifecycle_events l
            WHERE l.employee_id=@employee AND l.id=@entry AND l.xmin::text=@revision
                AND l.event_type='Scheduled transfer' AND l.effective_from<=@today AND " + TransferEventScope +
                " FOR UPDATE OF l", db, tx))
        {
            SetScope(plan);
            plan.Parameters.AddWithValue("employee", employee);
            plan.Parameters.AddWithValue("entry", entry);
            plan.Parameters.AddWithValue("revision", revision);
            plan.Parameters.AddWithValue("today", NpgsqlDbType.Date, current.Today);
            using var row = await plan.ExecuteReaderAsync(cancellation);
            if (!await row.ReadAsync(cancellation))
                throw new InvalidOperationException("This transfer is unavailable, was already applied, or is still in the future.");
            text = row.IsDBNull(0) ? "{}" : row.GetString(0);
            reason = row.IsDBNull(1) ? "Applied scheduled transfer" : row.GetString(1);
            due = row.GetDateTime(2);
        }

        var planState = System.Text.Json.Nodes.JsonNode.Parse(text) as System.Text.Json.Nodes.JsonObject;
        if (planState?["changes"] is not System.Text.Json.Nodes.JsonObject proposed ||
            planState["previous"] is not System.Text.Json.Nodes.JsonObject original || proposed.Count == 0 ||
            proposed.Any(item => item.Key is not ("department_id" or "designation_id" or "reporting_manager_id" or "shift_id")) ||
            !new HashSet<string>(proposed.Select(item => item.Key)).SetEquals(original.Select(item => item.Key)))
            throw new InvalidOperationException("This transfer requires the full organization transfer workflow.");
        var previous = TransferValues(current.Department, current.Designation, proposed.ContainsKey("reporting_manager_id"), current.Manager, proposed.ContainsKey("shift_id"), current.Shift);
        if (original.Any(item => previous[item.Key] != item.Value?.GetValue<int>()))
            throw new InvalidOperationException("Assignments changed since scheduling. Review and create a new transfer.");
        var destination = new Dictionary<string, int?>(previous);
        foreach (var item in proposed)
            destination[item.Key] = item.Value?.GetValue<int>();
        var draft = new EmployeeTransferDraft(destination["department_id"], destination["designation_id"], due, reason,
            destination.TryGetValue("reporting_manager_id", out var newManager), newManager,
            destination.TryGetValue("shift_id", out var newShift), newShift);
        await CheckTransferDestinationAsync(db, tx, employee, current, draft, true, cancellation);
        await UpdateTransferEmployeeAsync(db, tx, actor.Id, employee, current, draft, cancellation);
        planState["state"] = "applied";
        using var update = new NpgsqlCommand(@"UPDATE public.employee_lifecycle_events
            SET event_type='Transfer applied',remarks=@remarks WHERE id=@entry", db, tx);
        update.Parameters.AddWithValue("entry", entry);
        update.Parameters.AddWithValue("remarks", planState.ToJsonString());
        await update.ExecuteNonQueryAsync(cancellation);
        await AuditTransferAsync(db, tx, employee, actor.Id, "SCHEDULED_TRANSFER_APPLIED", reason,
            previous, destination, cancellation);
        await tx.CommitAsync(cancellation);
    }

    private async Task<DesktopActor> AuthorizeTransferAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        bool write, CancellationToken cancellation)
    {
        var actor = await AuthorizeAsync(db, tx, write, cancellation);
        await DesktopModuleAccess.RequireAsync(db, tx, settings.OrganizationId,
            settings.BranchId!.Value, actor, "hrms", "view", "employee_view");
        if (!actor.CanWriteBranch)
            throw new UnauthorizedAccessException("This branch is read-only.");
        if (write)
        {
            using var serialize = new NpgsqlCommand(
                "SELECT pg_advisory_xact_lock(hashtext('desktop-employee-transfers'),@branch)", db, tx);
            SetScope(serialize);
            await serialize.ExecuteNonQueryAsync(cancellation);
        }
        return actor;
    }

    private async Task<TransferEmployee> ReadTransferEmployeeAsync(NpgsqlConnection db, NpgsqlTransaction tx, int employee,
        bool locked, CancellationToken cancellation)
    {
        using var query = new NpgsqlCommand(@"
            SELECT e.department_id,e.designation_id,e.reporting_manager_id,e.status,e.xmin::text,
                (clock_timestamp() AT TIME ZONE coalesce(nullif(
                    (SELECT default_timezone FROM public.companies WHERE id=@company),''),'Asia/Kolkata'))::date::timestamp,
                coalesce((SELECT d.name FROM public.departments d WHERE d.id=e.department_id AND d.branch_id=@branch),'Unassigned'),
                coalesce((SELECT g.name FROM public.designations g JOIN public.departments d ON d.id=g.department_id
                    WHERE g.id=e.designation_id AND d.branch_id=@branch),'Unassigned'),
                coalesce((SELECT concat_ws(' ',m.first_name,m.last_name) FROM public.employees m
                    WHERE m.id=e.reporting_manager_id AND m.branch_id=@branch),'Unassigned'),
                e.shift_id,coalesce((SELECT s.name FROM public.shifts s WHERE s.id=e.shift_id AND " + TransferShiftScope + @"),'Unassigned')" + ScopedEmployees +
            " AND e.id=@employee" + (locked ? " FOR UPDATE OF e" : ""), db, tx);
        SetScope(query);
        query.Parameters.AddWithValue("employee", employee);
        using var row = await query.ExecuteReaderAsync(cancellation);
        if (!await row.ReadAsync(cancellation))
            throw new InvalidOperationException("The employee is unavailable in this branch.");
        return new(row.IsDBNull(0) ? null : (int?)row.GetInt32(0), row.IsDBNull(1) ? null : (int?)row.GetInt32(1),
            row.IsDBNull(2) ? null : (int?)row.GetInt32(2), row.IsDBNull(9) ? null : (int?)row.GetInt32(9),
            row.IsDBNull(3) ? null : row.GetString(3), row.GetString(4),
            row.GetDateTime(5), row.GetString(6), row.GetString(7), row.GetString(8), row.GetString(10));
    }

    private async Task<(string Department, string Designation, string Manager, string Shift)> CheckTransferDestinationAsync(NpgsqlConnection db,
        NpgsqlTransaction tx, int employee, TransferEmployee current, EmployeeTransferDraft draft, bool locked, CancellationToken cancellation)
    {
        bool placementChanged = draft.Department != current.Department || draft.Designation != current.Designation;
        if (placementChanged && draft.Department is null && draft.Designation.HasValue)
            throw new InvalidOperationException("Choose the department for the designation.");
        string department = placementChanged ? "Unassigned" : current.DepartmentName;
        string designation = placementChanged ? "Unassigned" : current.DesignationName;
        if (placementChanged && draft.Department.HasValue)
        {
            using var dept = new NpgsqlCommand("SELECT d.name" + CreateDepartmentScope +
                " AND d.id=@department" + (locked ? " FOR SHARE OF d" : ""), db, tx);
            SetScope(dept);
            dept.Parameters.AddWithValue("department", draft.Department.Value);
            department = await dept.ExecuteScalarAsync(cancellation) as string
                ?? throw new InvalidOperationException("Choose an active department in the selected branch.");
        }
        if (placementChanged && draft.Designation.HasValue)
        {
            using var role = new NpgsqlCommand("SELECT g.name" + TransferDesignationScope +
                " AND g.id=@designation AND g.department_id=@department" + (locked ? " FOR SHARE OF g" : ""), db, tx);
            SetScope(role);
            role.Parameters.AddWithValue("department", draft.Department!.Value);
            role.Parameters.AddWithValue("designation", draft.Designation.Value);
            designation = await role.ExecuteScalarAsync(cancellation) as string
                ?? throw new InvalidOperationException("Choose an active designation from the selected department.");
        }
        string manager = draft.ChangeManager
            ? await ValidateTransferManagerAsync(db, tx, employee, draft.Manager, locked, cancellation) : current.ManagerName;
        string shift = draft.ChangeShift ? "Unassigned" : current.ShiftName;
        if (draft.ChangeShift && draft.Shift.HasValue)
        {
            using var lookup = new NpgsqlCommand("SELECT s.name FROM public.shifts s WHERE s.id=@shift AND s.is_active AND " +
                TransferShiftScope + (locked ? " FOR SHARE OF s" : ""), db, tx);
            SetScope(lookup);
            lookup.Parameters.AddWithValue("shift", draft.Shift.Value);
            shift = await lookup.ExecuteScalarAsync(cancellation) as string
                ?? throw new InvalidOperationException("Choose an active shift available in this branch.");
        }
        return (department, designation, manager, shift);
    }

    private static EmployeeTransferDraft ValidateTransferDraft(EmployeeTransferDraft draft)
    {
        string reason = draft.Reason.Trim();
        if (reason.Length is < 3 or > 1000)
            throw new InvalidOperationException("Enter a reason of 3 to 1,000 characters.");
        return draft with { Reason = reason, EffectiveFrom = draft.EffectiveFrom.Date };
    }

    private static EmployeeTransferPreview BuildTransferPreview(int actor, int employee, TransferEmployee current,
        EmployeeTransferDraft draft, (string Department, string Designation, string Manager, string Shift) destination)
    {
        if (draft.EffectiveFrom < current.Today)
            throw new InvalidOperationException("Choose today or a future effective date.");
        if (draft.Department == current.Department && draft.Designation == current.Designation &&
            (!draft.ChangeManager || draft.Manager == current.Manager) && (!draft.ChangeShift || draft.Shift == current.Shift))
            throw new InvalidOperationException("Choose a different department, designation, manager or shift.");
        using var sha = SHA256.Create();
        string raw = JsonSerializer.Serialize(new { actor, employee, current.Revision, current.Today, draft, destination.Department, destination.Designation, destination.Manager, destination.Shift });
        string revision = BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(raw))).Replace("-", "");
        return new(revision, draft.EffectiveFrom > current.Today,
            $"{current.DepartmentName} · {current.DesignationName} · {current.ManagerName} · {current.ShiftName}",
            $"{destination.Department} · {destination.Designation} · {destination.Manager} · {destination.Shift}");
    }

    private async Task UpdateTransferEmployeeAsync(NpgsqlConnection db, NpgsqlTransaction tx, int actor, int employee,
        TransferEmployee current, EmployeeTransferDraft draft, CancellationToken cancellation)
    {
        using var update = new NpgsqlCommand(@"UPDATE public.employees SET department_id=@department,designation_id=@designation,reporting_manager_id=@manager,shift_id=@shift,
            updated_at=clock_timestamp() WHERE id=@employee", db, tx);
        update.Parameters.AddWithValue("employee", employee);
        AddTransferId(update, "department", draft.Department);
        AddTransferId(update, "designation", draft.Designation);
        int? manager = draft.ChangeManager ? draft.Manager : current.Manager;
        AddTransferId(update, "manager", manager);
        int? shift = draft.ChangeShift ? draft.Shift : current.Shift;
        AddTransferId(update, "shift", shift);
        await update.ExecuteNonQueryAsync(cancellation);
        foreach (var (key, before, after) in new[]
            { ("department_id", current.Department, draft.Department), ("designation_id", current.Designation, draft.Designation),
              ("reporting_manager_id", current.Manager, manager), ("shift_id", current.Shift, shift) })
            if (before != after)
                await RecordFieldAsync(db, tx, actor, employee, key, before?.ToString(CultureInfo.InvariantCulture),
                    after?.ToString(CultureInfo.InvariantCulture), cancellation);
    }

    private async Task AuditTransferAsync(NpgsqlConnection db, NpgsqlTransaction tx, int employee, int actor, string action, string reason,
        Dictionary<string, int?> previous, Dictionary<string, int?> changes, CancellationToken cancellation)
    {
        using var audit = new NpgsqlCommand(@"
            INSERT INTO public.audit_logs(organization_id,user_id,actor_email,actor_authenticated,method,endpoint,status_code,
                  entity_type,entity_id,action,description,module,old_values,new_values)
            SELECT @company,id,left(email,100),true,'POST','desktop/hrms/transfers',200,
                'employee',@employee,@action,@reason,'employees',@before,@after FROM public.users WHERE id=@actor RETURNING id", db, tx);
        SetScope(audit);
        audit.Parameters.AddWithValue("actor", actor);
        audit.Parameters.AddWithValue("employee", employee);
        audit.Parameters.AddWithValue("action", action);
        audit.Parameters.AddWithValue("reason", reason);
        audit.Parameters.AddWithValue("before", JsonSerializer.Serialize(previous));
        audit.Parameters.AddWithValue("after", JsonSerializer.Serialize(changes));
        int id = (int)(await audit.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(db, tx, "audit_logs", id, cancellation);
    }

    private static Dictionary<string, int?> TransferValues(int? department, int? designation, bool includeManager, int? manager,
        bool includeShift, int? shift)
    {
        var values = new Dictionary<string, int?> { ["department_id"] = department, ["designation_id"] = designation };
        if (includeManager)
            values["reporting_manager_id"] = manager;
        if (includeShift)
            values["shift_id"] = shift;
        return values;
    }

    private const string TransferShiftScope = @"NOT EXISTS(
        SELECT 1 FROM public.suite_branch_ownership o WHERE o.resource_table='shifts' AND o.resource_key=s.id::text
            AND (o.company_id<>@company OR o.branch_id<>@branch))";

    private static string TransferShiftLabel(string? remarks, Dictionary<int, string> names)
    {
        if (remarks is null || string.IsNullOrWhiteSpace(remarks))
            return "";
        try
        {
            using var state = JsonDocument.Parse(remarks);
            if (state.RootElement.ValueKind == JsonValueKind.Object &&
                state.RootElement.TryGetProperty("changes", out var changes) && changes.ValueKind == JsonValueKind.Object &&
                changes.TryGetProperty("shift_id", out var shift))
            {
                if (shift.ValueKind == JsonValueKind.Null)
                    return "Unassigned";
                if (shift.ValueKind == JsonValueKind.Number && shift.TryGetInt32(out int id))
                    return names.TryGetValue(id, out string? name) ? name ?? "" : "Unavailable shift";
            }
        }
        catch (JsonException) { }
        return "";
    }

    private const string ManagerEligibility = @"
        AND e.status IN ('Active','Probation') AND lower(trim(coalesce(e.employment_type,'')))<>'intern'
        AND EXISTS (
          SELECT 1 FROM public.users u LEFT JOIN public.roles r ON r.id=u.role_id
          WHERE u.id=e.user_id AND u.is_active AND lower(replace(replace(trim(coalesce(r.name,'')),'-','_'),' ','_'))<>'intern'
            AND (u.is_superuser OR lower(replace(replace(trim(coalesce(r.name,'')),'-','_'),' ','_')) IN
               ('super_admin','superadmin','ceo','hr','hr_admin','hr_manager','project_manager','pms_project_manager'))
            AND NOT EXISTS (SELECT 1 FROM public.suite_access_memberships a WHERE a.user_id=u.id AND a.company_id=@company AND NOT a.active)
        )";

    private async Task<string> ValidateTransferManagerAsync(NpgsqlConnection db, NpgsqlTransaction tx, int employee,
        int? person, bool locked, CancellationToken cancellation)
    {
        if (!person.HasValue)
            return "Unassigned";
        if (person.Value == employee)
            throw new InvalidOperationException("An employee cannot report to themselves.");
        using var choice = new NpgsqlCommand("SELECT concat_ws(' ',e.first_name,e.last_name)" + ScopedEmployees +
            ManagerEligibility + " AND e.id=@manager" + (locked ? " FOR SHARE OF e" : ""), db, tx);
        SetScope(choice);
        choice.Parameters.AddWithValue("manager", person.Value);
        if (await choice.ExecuteScalarAsync(cancellation) is not string label)
            throw new InvalidOperationException("Choose an eligible active reporting manager in this branch.");
        using var cycle = new NpgsqlCommand(@"
            WITH RECURSIVE chain(id) AS (
                SELECT @manager
                UNION
                SELECT e.reporting_manager_id FROM public.employees e JOIN chain c ON c.id=e.id
                JOIN public.branches b ON b.id=e.branch_id AND b.company_id=@company
                WHERE e.reporting_manager_id IS NOT NULL AND e.deleted_at IS NULL
            ) SELECT EXISTS(SELECT 1 FROM chain WHERE id=@employee)", db, tx);
        SetScope(cycle);
        cycle.Parameters.AddWithValue("manager", person.Value);
        cycle.Parameters.AddWithValue("employee", employee);
        if (await cycle.ExecuteScalarAsync(cancellation) is true)
            throw new InvalidOperationException("This reporting manager would create a reporting cycle.");
        return label;
    }

    private static void AddTransferId(NpgsqlCommand query, string key, int? value) =>
        query.Parameters.Add(key, NpgsqlDbType.Integer).Value = (object?)value ?? DBNull.Value;
}
