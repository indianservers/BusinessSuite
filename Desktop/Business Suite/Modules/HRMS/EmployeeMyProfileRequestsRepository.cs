using System.Data;
using Npgsql;

namespace Business_Suite;

internal sealed partial class EmployeeAdministrationRepository
{
    internal async Task<(DataTable Rows, string Employee, bool CanSubmit)> ReadMyProfileRequestsAsync(string status,
        CancellationToken cancellation)
    {
        if (status is not ("" or "Pending" or "Approved" or "Rejected"))
            throw new InvalidOperationException("Choose a request status.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await settings.RequireActorAsync(db, tx, cancellation);
        var owner = await ReadSubmissionTargetAsync(db, tx, actor, null, false, cancellation);
        using var query = new NpgsqlCommand(@"
            SELECT r.id,r.request_type,r.status,r.created_at,r.reviewed_at,r.reason,r.review_remarks,
                coalesce((SELECT string_agg(replace(k,'_',' '), ', ' ORDER BY k)
                    FROM jsonb_object_keys(CASE WHEN json_typeof(r.field_changes_json)='object'
                        THEN r.field_changes_json::jsonb ELSE '{}'::jsonb END) AS keys(k)), '') AS fields
            FROM public.employee_change_requests r WHERE " + RequestScope + @"
                AND (@status='' OR r.status=@status)
            ORDER BY r.id DESC LIMIT 300", db, tx);
        SetScope(query);
        query.Parameters.AddWithValue("employee", owner.Employee);
        query.Parameters.AddWithValue("status", status);
        return (await ReadTableAsync(query, cancellation), owner.Name, actor.CanWriteBranch);
    }
}
