using System.Data;
using System.Text.Json;
using Npgsql;

namespace Business_Suite;

internal sealed partial class EmployeeAdministrationRepository
{
    private static readonly HashSet<string> ApplicableRequestFields = new(StringComparer.Ordinal)
    {
        "present_city", "present_state", "present_pincode", "permanent_city", "permanent_state", "permanent_pincode",
        "emergency_contact_relation"
    };

    private const string RequestScope = @" r.employee_id=@employee AND (r.organization_id IS NULL OR r.organization_id=@company)
        AND NOT EXISTS (SELECT 1 FROM public.suite_branch_ownership o WHERE o.resource_table='employee_change_requests'
            AND o.resource_key=r.id::text AND (o.company_id<>@company OR o.branch_id<>@branch))";

    internal async Task<(DataTable Rows, bool Writable)> ReadProfileRequestsAsync(int employee, string status, CancellationToken cancellation)
    {
        if (status is not ("" or "Pending" or "Approved" or "Rejected"))
            throw new InvalidOperationException("Choose a request status.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await AuthorizeAsync(db, tx, false, cancellation);
        await ReadRequestEmployeeAsync(db, tx, employee, false, cancellation);
        using var query = new NpgsqlCommand(@"
            SELECT r.id,r.request_type,r.status,r.effective_date::timestamp,r.created_at,r.reviewed_at,r.xmin::text AS revision,
                coalesce(f.fields,'') AS fields,coalesce(f.comparison,'') AS comparison,
                coalesce(f.supported,false) AS supported,
                (r.requested_by IS DISTINCT FROM @actor OR @superuser) AS can_review
            FROM public.employee_change_requests r
            LEFT JOIN LATERAL (
                SELECT string_agg(replace(k,'_',' '), ', ' ORDER BY k) AS fields,
                   string_agg(replace(k,'_',' ')||': ' ||coalesce(r.old_value_json::jsonb->>k,'[empty]')||
                       ' → '||coalesce(data.changes->>k,'[empty]'),chr(10) ORDER BY k)
                       FILTER(WHERE k=ANY(@allowed) AND jsonb_typeof(data.changes->k) IN ('string','null')
                           AND coalesce(jsonb_typeof(r.old_value_json::jsonb->k),'null') IN ('string','null')) AS comparison,
                   bool_and(k=ANY(@allowed) AND jsonb_typeof(data.changes->k) IN ('string','null')) AS supported
                FROM (SELECT CASE WHEN json_typeof(r.field_changes_json)='object' THEN r.field_changes_json::jsonb
                    ELSE '{}'::jsonb END AS changes) data
                CROSS JOIN LATERAL jsonb_object_keys(data.changes) AS keys(k)
            ) f ON true
            WHERE " + RequestScope + @" AND (@status='' OR r.status=@status)
            ORDER BY r.id DESC LIMIT 300", db, tx);
        SetScope(query);
        query.Parameters.AddWithValue("employee", employee);
        query.Parameters.AddWithValue("status", status);
        query.Parameters.AddWithValue("actor", actor.Id);
        query.Parameters.AddWithValue("superuser", actor.IsSuperuser);
        query.Parameters.AddWithValue("allowed", ApplicableRequestFields.ToArray());
        return (await ReadTableAsync(query, cancellation), actor.CanWriteBranch);
    }

    internal async Task ReviewProfileRequestAsync(int employee, int request, string revision, bool approve, string? remarks,
        CancellationToken cancellation)
    {
        remarks = Clean(remarks, 1000);
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await AuthorizeAsync(db, tx, true, cancellation);
        await ReadRequestEmployeeAsync(db, tx, employee, false, cancellation);
        string payload;
        string originals;
        DateTime? effective;
        using (var locked = new NpgsqlCommand(@"
            SELECT r.field_changes_json::text,coalesce(r.old_value_json::text,'{}'),r.effective_date::timestamp,
                r.requested_by IS NOT DISTINCT FROM @actor
            FROM public.employee_change_requests r WHERE " + RequestScope + @"
                AND r.id=@request AND r.xmin::text=@revision AND r.status='Pending' FOR UPDATE OF r", db, tx))
        {
            SetScope(locked);
            locked.Parameters.AddWithValue("employee", employee);
            locked.Parameters.AddWithValue("request", request);
            locked.Parameters.AddWithValue("revision", revision);
            locked.Parameters.AddWithValue("actor", actor.Id);
            using var result = await locked.ExecuteReaderAsync(cancellation);
            if (!await result.ReadAsync(cancellation))
                throw new InvalidOperationException("The request changed or was reviewed. Refresh the pending list.");
            if (!actor.IsSuperuser && result.GetBoolean(3))
                throw new UnauthorizedAccessException("You cannot review your own profile change request.");
            payload = result.GetString(0);
            originals = result.GetString(1);
            effective = result.IsDBNull(2) ? (DateTime?)null : result.GetDateTime(2);
        }

        var (current, today) = await ReadRequestEmployeeAsync(db, tx, employee, true, cancellation);
        actor = await AuthorizeAsync(db, tx, true, cancellation);
        if (approve)
        {
            if (effective.HasValue && effective.Value.Date > today.Date)
                throw new InvalidOperationException("Future-dated requests require the scheduled change workflow.");
            using var proposed = JsonDocument.Parse(payload);
            using var before = JsonDocument.Parse(originals);
            using var snapshot = JsonDocument.Parse(current);
            if (proposed.RootElement.ValueKind != JsonValueKind.Object || before.RootElement.ValueKind != JsonValueKind.Object
                || !proposed.RootElement.EnumerateObject().Any())
                throw new InvalidOperationException("This request requires the full profile review workflow.");
            var changes = new Dictionary<string, string?>();
            foreach (var field in proposed.RootElement.EnumerateObject())
            {
                if (!ApplicableRequestFields.Contains(field.Name) || field.Value.ValueKind is not (JsonValueKind.String or JsonValueKind.Null))
                    throw new InvalidOperationException("This request includes fields that require the full profile review workflow.");
                var old = snapshot.RootElement.GetProperty(field.Name).GetString();
                if (!before.RootElement.TryGetProperty(field.Name, out var baseline)
                    || baseline.ValueKind is not (JsonValueKind.String or JsonValueKind.Null) || baseline.GetString() != old)
                    throw new InvalidOperationException("Employee details changed or the request has no prior value. Review a fresh request.");
                if (changes.ContainsKey(field.Name))
                    throw new InvalidOperationException("The request contains duplicate fields.");
                changes.Add(field.Name, Clean(field.Value.GetString(), 200));
            }

            foreach (var field in changes)
            {
                using var apply = new NpgsqlCommand("UPDATE public.employees SET " + field.Key +
                    "=@value,updated_at=clock_timestamp() WHERE id=@employee", db, tx);
                AddText(apply, "value", field.Value);
                apply.Parameters.AddWithValue("employee", employee);
                await apply.ExecuteNonQueryAsync(cancellation);
                var old = snapshot.RootElement.GetProperty(field.Key).GetString();
                if (old != field.Value)
                    await RecordFieldAsync(db, tx, actor.Id, employee, field.Key, old, field.Value, cancellation);
            }
        }

        using var review = new NpgsqlCommand(@"
            UPDATE public.employee_change_requests SET status=@status,reviewed_by=@actor,reviewed_at=clock_timestamp(),
                review_remarks=@remarks WHERE id=@request;
            INSERT INTO public.audit_logs(organization_id,user_id,actor_email,actor_authenticated,method,endpoint,status_code,
                entity_type,entity_id,action,description,module)
            SELECT @company,id,left(email,100),true,'PUT','desktop/employees/change-requests/review',200,
                'employee_change_request',@request,@event,'Reviewed profile change request','employees'
            FROM public.users WHERE id=@actor RETURNING id", db, tx);
        SetScope(review);
        review.Parameters.AddWithValue("request", request);
        review.Parameters.AddWithValue("actor", actor.Id);
        review.Parameters.AddWithValue("status", approve ? "Approved" : "Rejected");
        review.Parameters.AddWithValue("event", approve ? "PROFILE_CHANGE_APPROVED" : "PROFILE_CHANGE_REJECTED");
        AddText(review, "remarks", remarks);
        int audit = (int)(await review.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(db, tx, "audit_logs", audit, cancellation);
        await tx.CommitAsync(cancellation);
    }

    private async Task<(string Current, DateTime Today)> ReadRequestEmployeeAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        int employee, bool write, CancellationToken cancellation)
    {
        using var query = new NpgsqlCommand(@"
            SELECT jsonb_build_object('present_city',e.present_city,'present_state',e.present_state,
                'present_pincode',e.present_pincode,'permanent_city',e.permanent_city,'permanent_state',e.permanent_state,
                'permanent_pincode',e.permanent_pincode,'emergency_contact_relation',e.emergency_contact_relation)::text,
                (clock_timestamp() AT TIME ZONE coalesce(nullif(
                    (SELECT default_timezone FROM public.companies WHERE id=@company),''),'Asia/Kolkata'))::date::timestamp"
                + ScopedEmployees + " AND e.id=@employee" + (write ? " FOR UPDATE OF e" : ""), db, tx);
        SetScope(query);
        query.Parameters.AddWithValue("employee", employee);
        using var row = await query.ExecuteReaderAsync(cancellation);
        if (!await row.ReadAsync(cancellation))
            throw new InvalidOperationException("The employee profile is unavailable.");
        return (row.GetString(0), row.GetDateTime(1));
    }
}
