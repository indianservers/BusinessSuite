using System.Data;
using Npgsql;

namespace Business_Suite;

internal sealed record EmployeeDocumentReview(string Status, string? Reviewer, string? Company, string? Notes);

internal sealed partial class EmployeeAdministrationRepository
{
    private const string DocumentResource = "employee_documents";

    internal async Task<(DataTable Rows, string Revision, bool Writable)> ReadDocumentsAsync(int employee, CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await AuthorizeAsync(db, tx, false, cancellation);
        string revision = await ReadQualificationRevisionAsync(db, tx, employee, false, cancellation);
        await RequireDocumentAccessAsync(db, tx, actor, employee, cancellation);
        using var query = new NpgsqlCommand(@"
            SELECT ed.id,ed.document_type,coalesce(nullif(ed.document_name,''),ed.document_type) AS document_name,
                ed.expiry_date::timestamp,coalesce(nullif(ed.verification_status,''),
                    CASE WHEN ed.is_verified THEN 'Verified' ELSE 'Pending' END) AS verification_status,
                ed.verified_at,ed.verifier_name,ed.verifier_company,ed.verification_notes
            FROM public.employee_documents ed WHERE ed.employee_id=@employee" + QualificationScope +
                " ORDER BY ed.id DESC", db, tx);
        SetScope(query);
        query.Parameters.AddWithValue("resource", DocumentResource);
        query.Parameters.AddWithValue("employee", employee);
        return (await ReadTableAsync(query, cancellation), revision, actor.CanWriteBranch);
    }

    internal async Task VerifyDocumentAsync(int employee, int document, string revision, EmployeeDocumentReview draft,
        CancellationToken cancellation)
    {
        if (draft.Status is not ("Pending" or "Verified" or "Rejected"))
            throw new InvalidOperationException("Choose Pending, Verified or Rejected.");
        string? notes = string.IsNullOrWhiteSpace(draft.Notes) ? null : draft.Notes?.Trim();
        if (draft.Status == "Rejected" && notes is null)
            throw new InvalidOperationException("Enter a reason for rejecting the document.");
        if (notes?.Any(c => char.IsControl(c) && c is not ('\r' or '\n' or '\t')) == true)
            throw new InvalidOperationException("Verification notes contain unsupported characters.");
        string? reviewer = Clean(draft.Reviewer, 150);
        string? company = Clean(draft.Company, 200);

        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await AuthorizeAsync(db, tx, true, cancellation);
        if (revision != await ReadQualificationRevisionAsync(db, tx, employee, true, cancellation))
            throw new InvalidOperationException("The employee profile changed. Refresh before reviewing this document.");
        actor = await AuthorizeAsync(db, tx, true, cancellation);
        await RequireDocumentAccessAsync(db, tx, actor, employee, cancellation);
        var before = await QualificationValuesAsync(db, tx, employee, document, DocumentResource, cancellation);
        using var update = new NpgsqlCommand(@"
            UPDATE public.employee_documents ed SET verification_status=@status,is_verified=@verified,
                verified_by=@actor,verified_at=clock_timestamp(),verifier_name=@reviewer,verifier_company=@reviewer_company,
                verification_notes=@notes WHERE ed.id=@document AND ed.employee_id=@employee" + QualificationScope, db, tx);
        SetScope(update);
        update.Parameters.AddWithValue("resource", DocumentResource);
        update.Parameters.AddWithValue("employee", employee);
        update.Parameters.AddWithValue("document", document);
        update.Parameters.AddWithValue("status", draft.Status);
        update.Parameters.AddWithValue("verified", draft.Status == "Verified");
        update.Parameters.AddWithValue("actor", actor.Id);
        AddText(update, "reviewer", reviewer);
        AddText(update, "reviewer_company", company);
        AddText(update, "notes", notes);
        if (await update.ExecuteNonQueryAsync(cancellation) != 1)
            throw new InvalidOperationException("The document is unavailable.");
        var after = await QualificationValuesAsync(db, tx, employee, document, DocumentResource, cancellation);
        await FinishQualificationAsync(db, tx, actor.Id, employee, document, true, false, DocumentResource,
            before, after, cancellation);
        await tx.CommitAsync(cancellation);
    }

    private async Task RequireDocumentAccessAsync(NpgsqlConnection db, NpgsqlTransaction tx, DesktopActor actor, int employee,
        CancellationToken cancellation)
    {
        using var own = new NpgsqlCommand("SELECT coalesce(e.user_id=@actor,false)" + ScopedEmployees + " AND e.id=@employee", db, tx);
        SetScope(own);
        own.Parameters.AddWithValue("employee", employee);
        own.Parameters.AddWithValue("actor", actor.Id);
        bool isOwn = await own.ExecuteScalarAsync(cancellation) is true;
        if (!await CanReadEmployeeDocumentsAsync(db, tx, actor, isOwn))
            throw new UnauthorizedAccessException("Employee document review requires sensitive employee access.");
    }

    private async Task<bool> CanReadEmployeeDocumentsAsync(NpgsqlConnection db, NpgsqlTransaction tx, DesktopActor actor, bool ownProfile)
    {
        if (ownProfile)
            return true;
        try
        {
            var grant = await DesktopModuleAccess.RequireAsync(db, tx, settings.OrganizationId, settings.BranchId!.Value,
                actor, "hrms", "view", "employee_sensitive_view");
            return grant.Scope is "organization" or "branch";
        }
        catch (UnauthorizedAccessException) { return false; }
    }
}
