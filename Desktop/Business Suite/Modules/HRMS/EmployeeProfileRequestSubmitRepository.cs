using System.Data;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record EmployeeRequestSnapshot(int Employee, string Name, string Revision, Dictionary<string, string?> Values);

internal sealed partial class EmployeeAdministrationRepository
{
    internal async Task<EmployeeRequestSnapshot> ReadRequestSubmissionAsync(int? employee, CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await settings.RequireActorAsync(db, tx, cancellation);
        if (!actor.CanWriteBranch)
            throw new UnauthorizedAccessException("Write access requires a writable branch.");
        return await ReadSubmissionTargetAsync(db, tx, actor, employee, false, cancellation);
    }

    internal async Task<int> SubmitProfileRequestAsync(int? employee, string revision, string field, string? proposed,
        string? reason, CancellationToken cancellation)
    {
        if (!ApplicableRequestFields.Contains(field))
            throw new InvalidOperationException("Choose an editable profile field.");
        proposed = Clean(proposed, 200);
        reason = Clean(reason, 1000) ?? "Employee self-service profile update";
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await settings.VerifyWriteTargetAsync(db, tx, cancellation);
        var current = await ReadSubmissionTargetAsync(db, tx, actor, employee, true, cancellation);
        if (revision != current.Revision)
            throw new InvalidOperationException("The employee profile changed. Reload the current value before submitting.");
        if (current.Values[field] == proposed)
            throw new InvalidOperationException("Enter a new value before submitting.");

        using (var duplicate = new NpgsqlCommand(@"
            SELECT EXISTS (SELECT 1 FROM public.employee_change_requests r WHERE " + RequestScope + @"
               AND r.status='Pending' AND (r.field_name=@field OR (
                   jsonb_typeof(r.field_changes_json::jsonb)='object' AND jsonb_exists(r.field_changes_json::jsonb,@field))))", db, tx))
        {
            SetScope(duplicate);
            duplicate.Parameters.AddWithValue("employee", current.Employee);
            duplicate.Parameters.AddWithValue("field", field);
            if (await duplicate.ExecuteScalarAsync(cancellation) is true)
                throw new InvalidOperationException("A pending request already exists for this field.");
        }

        using var insert = new NpgsqlCommand(@"
            INSERT INTO public.employee_change_requests(organization_id,employee_id,request_type,field_name,effective_date,
                field_changes_json,old_value_json,new_value_json,status,reason,requested_by)
            SELECT @company,@employee,'Profile Update',@field,
                (clock_timestamp() AT TIME ZONE coalesce(nullif(c.default_timezone,''),'Asia/Kolkata'))::date,
                @proposed,@original,@proposed,'Pending',@reason,@actor
            FROM public.companies c WHERE c.id=@company RETURNING id", db, tx);
        SetScope(insert);
        insert.Parameters.AddWithValue("employee", current.Employee);
        insert.Parameters.AddWithValue("field", field);
        insert.Parameters.AddWithValue("reason", reason);
        insert.Parameters.AddWithValue("actor", actor.Id);
        insert.Parameters.AddWithValue("proposed", NpgsqlDbType.Json,
            JsonSerializer.Serialize(new Dictionary<string, string?> { [field] = proposed }));
        insert.Parameters.AddWithValue("original", NpgsqlDbType.Json,
            JsonSerializer.Serialize(new Dictionary<string, string?> { [field] = current.Values[field] }));
        int id = (int)(await insert.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(db, tx, "employee_change_requests", id, cancellation);

        using var audit = new NpgsqlCommand(@"
            INSERT INTO public.audit_logs(organization_id,user_id,actor_email,actor_authenticated,method,endpoint,status_code,
                entity_type,entity_id,action,description,module)
            SELECT @company,id,left(email,100),true,'POST','desktop/employees/change-requests',201,
                'employee_change_request',@request,'PROFILE_CHANGE_SUBMITTED','Submitted profile change request','employees'
            FROM public.users WHERE id=@actor RETURNING id", db, tx);
        SetScope(audit);
        audit.Parameters.AddWithValue("request", id);
        audit.Parameters.AddWithValue("actor", actor.Id);
        int auditId = (int)(await audit.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(db, tx, "audit_logs", auditId, cancellation);
        await tx.CommitAsync(cancellation);
        return id;
    }

    private async Task<EmployeeRequestSnapshot> ReadSubmissionTargetAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        DesktopActor actor, int? employee, bool write, CancellationToken cancellation)
    {
        if (!settings.BranchId.HasValue)
            throw new InvalidOperationException("Choose a branch before submitting a profile change.");
        using var query = new NpgsqlCommand(@"
            SELECT e.id,concat_ws(' ',e.first_name,e.last_name),e.xmin::text,coalesce(e.user_id=@actor,false),
                jsonb_build_object('present_city',e.present_city,'present_state',e.present_state,
                    'present_pincode',e.present_pincode,'permanent_city',e.permanent_city,'permanent_state',e.permanent_state,
                    'permanent_pincode',e.permanent_pincode,'emergency_contact_relation',e.emergency_contact_relation)::text"
            + ScopedEmployees + " AND ((@employee IS NULL AND e.user_id=@actor) OR e.id=@employee) ORDER BY e.id LIMIT 2"
            + (write ? " FOR UPDATE OF e" : ""), db, tx);
        SetScope(query);
        query.Parameters.AddWithValue("actor", actor.Id);
        query.Parameters.Add("employee", NpgsqlDbType.Integer).Value = (object?)employee ?? DBNull.Value;
        EmployeeRequestSnapshot result;
        bool own;
        using (var rows = await query.ExecuteReaderAsync(cancellation))
        {
            if (!await rows.ReadAsync(cancellation))
                throw new InvalidOperationException(employee.HasValue ? "The employee is unavailable in the selected branch."
                    : "Your login does not have a linked employee in the selected branch.");
            own = rows.GetBoolean(3);
            result = new EmployeeRequestSnapshot(rows.GetInt32(0), rows.GetString(1), rows.GetString(2),
                JsonSerializer.Deserialize<Dictionary<string, string?>>(rows.GetString(4))!);
            if (await rows.ReadAsync(cancellation))
                throw new InvalidOperationException("Your login is linked to more than one employee in this branch.");
        }
        if (!own)
            await AuthorizeAsync(db, tx, write, cancellation);
        return result;
    }
}
