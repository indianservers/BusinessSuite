using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record EmployeeExitInterviewDraft(DateTime? Date, string? Reason, int? Job, int? Management,
    int? Environment, int? Growth, bool? Rejoin, string? Feedback, string? Suggestions);
internal sealed record EmployeeExitInterviewView(DataTable Records, bool CanAdd);

internal sealed partial class EmployeeAdministrationRepository
{
    private const string ExitInterviewOwnership = @"EXISTS(SELECT 1 FROM public.suite_branch_ownership o
        WHERE o.resource_table='exit_interviews' AND o.resource_key=i.id::text AND o.company_id=@company AND o.branch_id=@branch)";

    internal async Task<EmployeeExitInterviewView> ReadExitInterviewsAsync(int employee, int exit, CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await AuthorizeExitAsync(db, tx, false, cancellation);
        await ReadExitEmployeeAsync(db, tx, employee, false, cancellation);
        await CheckExitInterviewCaseAsync(db, tx, employee, exit, false, cancellation);
        bool mayReadNarrative = false;
        try
        {
            var grant = await DesktopModuleAccess.RequireAsync(db, tx, settings.OrganizationId, settings.BranchId!.Value,
                actor, "hrms", "view", "exit_manage");
            mayReadNarrative = grant.Scope is "organization" or "branch";
        }
        catch (UnauthorizedAccessException) { }
        bool mayAdd = false;
        if (mayReadNarrative && actor.CanWriteBranch)
        {
            try
            {
                var grant = await DesktopModuleAccess.RequireAsync(db, tx, settings.OrganizationId, settings.BranchId!.Value,
                    actor, "hrms", "edit", "exit_manage");
                mayAdd = grant.Scope is "organization" or "branch";
            }
            catch (UnauthorizedAccessException) { }
        }

        using var query = new NpgsqlCommand(@"
            SELECT i.id,i.interview_date::timestamp,coalesce(i.conducted_by::text,'System') AS interviewer,
                CASE WHEN @details THEN i.reason_for_leaving END AS reason_for_leaving,
                CASE WHEN @details THEN i.job_satisfaction END AS job_satisfaction,
                CASE WHEN @details THEN i.management_satisfaction END AS management_satisfaction,
                CASE WHEN @details THEN i.work_environment_satisfaction END AS work_environment_satisfaction,
                CASE WHEN @details THEN i.growth_satisfaction END AS growth_satisfaction,
                CASE WHEN @details THEN i.would_rejoin END AS would_rejoin,
                CASE WHEN @details THEN i.feedback END AS feedback,CASE WHEN @details THEN i.suggestions END AS suggestions,
                i.created_at
            FROM public.exit_interviews i WHERE i.exit_record_id=@case AND " + ExitInterviewOwnership +
            " ORDER BY i.interview_date DESC NULLS LAST,i.id DESC LIMIT 100", db, tx);
        SetScope(query);
        query.Parameters.AddWithValue("case", exit);
        query.Parameters.AddWithValue("details", mayReadNarrative);
        return new(await ReadTableAsync(query, cancellation), mayAdd);
    }

    internal async Task<int> AddExitInterviewAsync(int employee, int exit, EmployeeExitInterviewDraft draft, CancellationToken cancellation)
    {
        string? reason = Clean(draft.Reason, 100);
        string? feedback = NormalizeExitNarrative(draft.Feedback);
        string? suggestions = NormalizeExitNarrative(draft.Suggestions);
        if (new[] { draft.Job, draft.Management, draft.Environment, draft.Growth }.Any(rating => rating is < 1 or > 10))
            throw new InvalidOperationException("Choose interview ratings from 1 to 10.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await AuthorizeExitAsync(db, tx, true, cancellation);
        await ReadExitEmployeeAsync(db, tx, employee, true, cancellation);
        await CheckExitInterviewCaseAsync(db, tx, employee, exit, true, cancellation);
        using var insert = new NpgsqlCommand(@"
            INSERT INTO public.exit_interviews(exit_record_id,conducted_by,interview_date,reason_for_leaving,
                job_satisfaction,management_satisfaction,work_environment_satisfaction,growth_satisfaction,
                would_rejoin,feedback,suggestions)
            VALUES(@case,@actor,@date,@reason,@job,@management,@environment,@growth,@rejoin,@feedback,@suggestions)
            RETURNING id", db, tx);
        insert.Parameters.AddWithValue("case", exit);
        insert.Parameters.AddWithValue("actor", actor.Id);
        insert.Parameters.Add("date", NpgsqlDbType.Date).Value = (object?)draft.Date?.Date ?? DBNull.Value;
        insert.Parameters.Add("rejoin", NpgsqlDbType.Boolean).Value = (object?)draft.Rejoin ?? DBNull.Value;
        AddTransferId(insert, "job", draft.Job);
        AddTransferId(insert, "management", draft.Management);
        AddTransferId(insert, "environment", draft.Environment);
        AddTransferId(insert, "growth", draft.Growth);
        AddText(insert, "reason", reason);
        AddText(insert, "feedback", feedback);
        AddText(insert, "suggestions", suggestions);
        int id = (int)(await insert.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(db, tx, "exit_interviews", id, cancellation);
        await RecordExitAuditAsync(db, tx, actor.Id, employee, "EXIT_INTERVIEW_RECORDED", "Exit interview recorded",
            new { exit_id = exit, interview_id = id }, cancellation);
        await tx.CommitAsync(cancellation);
        return id;
    }

    private async Task CheckExitInterviewCaseAsync(NpgsqlConnection db, NpgsqlTransaction tx, int employee, int exit,
        bool write, CancellationToken cancellation)
    {
        using var verify = new NpgsqlCommand("SELECT x.id FROM public.exit_records x WHERE x.employee_id=@employee AND x.id=@case AND "
            + ExitOwnership + (write ? " FOR UPDATE OF x" : ""), db, tx);
        SetScope(verify);
        verify.Parameters.AddWithValue("employee", employee);
        verify.Parameters.AddWithValue("case", exit);
        if (await verify.ExecuteScalarAsync(cancellation) is not int)
            throw new InvalidOperationException("The exit case is unavailable in this branch.");
    }

    private static string? NormalizeExitNarrative(string? value)
    {
        value = value?.Trim();
        if (value?.Any(ch => char.IsControl(ch) && ch is not ('\r' or '\n' or '\t')) == true)
            throw new InvalidOperationException("Interview notes contain unsupported characters.");
        return string.IsNullOrEmpty(value) ? null : value;
    }
}
