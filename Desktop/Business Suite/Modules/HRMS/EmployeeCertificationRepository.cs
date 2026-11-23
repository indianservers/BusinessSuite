using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record EmployeeCertificationDraft(string Name, string? Issuer, string? Type, string? Number,
    DateTime? Issued, DateTime? Expires, bool Renewable, string? Grade, string? VerificationUrl, string? DocumentUrl);

internal sealed partial class EmployeeAdministrationRepository
{
    private const string CertificationResource = "employee_certifications";

    internal async Task<(DataTable Rows, string Revision)> ReadCertificationsAsync(int employee, CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        await AuthorizeAsync(db, tx, false, cancellation);
        string revision = await ReadQualificationRevisionAsync(db, tx, employee, false, cancellation);
        using var query = new NpgsqlCommand(@"SELECT ed.id,ed.certification_name,ed.issuing_body,ed.certification_type,ed.certificate_number,
            ed.issue_date::timestamp,ed.expiry_date::timestamp,ed.is_renewable,ed.score_grade,ed.verification_url,ed.document_url
            FROM public.employee_certifications ed WHERE ed.employee_id=@employee" + QualificationScope +
            " ORDER BY ed.expiry_date NULLS LAST,ed.id DESC", db, tx);
        SetScope(query);
        query.Parameters.AddWithValue("resource", CertificationResource);
        query.Parameters.AddWithValue("employee", employee);
        return (await ReadTableAsync(query, cancellation), revision);
    }

    internal async Task<int> SaveCertificationAsync(int employee, string revision, int? record, EmployeeCertificationDraft? draft,
        CancellationToken cancellation)
    {
        if (draft is null && !record.HasValue)
            throw new InvalidOperationException("Select a certification to delete.");
        if (draft is not null)
        {
            draft = draft with { Name = Clean(draft.Name, 200) ?? "", Issuer = Clean(draft.Issuer, 200),
                Type = Clean(draft.Type, 50), Number = Clean(draft.Number, 100), Grade = Clean(draft.Grade, 50),
                VerificationUrl = Clean(draft.VerificationUrl, 500), DocumentUrl = Clean(draft.DocumentUrl, 500) };
            if (draft.Name.Length == 0)
                throw new InvalidOperationException("Enter a certification name.");
            if (draft.Issued.HasValue && draft.Expires.HasValue && draft.Expires.Value.Date < draft.Issued.Value.Date)
                throw new InvalidOperationException("Expiry date must be on or after issue date.");
        }

        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await AuthorizeAsync(db, tx, true, cancellation);
        if (revision != await ReadQualificationRevisionAsync(db, tx, employee, true, cancellation))
            throw new InvalidOperationException("The employee profile changed. Refresh before saving certifications.");
        await AuthorizeAsync(db, tx, true, cancellation);

        var before = record.HasValue ? await QualificationValuesAsync(db, tx, employee, record.Value, CertificationResource, cancellation) : new();
        using var write = new NpgsqlCommand(draft is null
            ? "DELETE FROM public.employee_certifications ed WHERE ed.id=@record AND ed.employee_id=@employee" + QualificationScope + " RETURNING id"
            : record.HasValue
                ? @"UPDATE public.employee_certifications ed SET certification_name=@name,issuing_body=@issuer,
                    certification_type=@type,certificate_number=@number,issue_date=@issued,expiry_date=@expires,
                    is_renewable=@renewable,score_grade=@grade,verification_url=@verification,document_url=@document
                    WHERE ed.id=@record AND ed.employee_id=@employee" + QualificationScope + " RETURNING id"
                : @"INSERT INTO public.employee_certifications(employee_id,certification_name,issuing_body,certification_type,
                    certificate_number,issue_date,expiry_date,is_renewable,score_grade,verification_url,document_url)
                    VALUES(@employee,@name,@issuer,@type,@number,@issued,@expires,@renewable,@grade,@verification,@document)
                    RETURNING id", db, tx);
        SetScope(write);
        write.Parameters.AddWithValue("resource", CertificationResource);
        write.Parameters.AddWithValue("employee", employee);
        write.Parameters.Add("record", NpgsqlDbType.Integer).Value = (object?)record ?? DBNull.Value;
        if (draft is not null)
        {
            AddText(write, "name", draft.Name);
            AddText(write, "issuer", draft.Issuer);
            AddText(write, "type", draft.Type);
            AddText(write, "number", draft.Number);
            AddText(write, "grade", draft.Grade);
            AddText(write, "verification", draft.VerificationUrl);
            AddText(write, "document", draft.DocumentUrl);
            write.Parameters.Add("issued", NpgsqlDbType.Date).Value = (object?)draft.Issued?.Date ?? DBNull.Value;
            write.Parameters.Add("expires", NpgsqlDbType.Date).Value = (object?)draft.Expires?.Date ?? DBNull.Value;
            write.Parameters.AddWithValue("renewable", draft.Renewable);
        }
        int id = await write.ExecuteScalarAsync(cancellation) is int saved ? saved
            : throw new InvalidOperationException("The certification is unavailable.");
        var after = draft is null ? new() : await QualificationValuesAsync(db, tx, employee, id, CertificationResource, cancellation);
        await FinishQualificationAsync(db, tx, actor.Id, employee, id, record.HasValue, draft is null, CertificationResource,
            before, after, cancellation);
        await tx.CommitAsync(cancellation);
        return id;
    }
}


