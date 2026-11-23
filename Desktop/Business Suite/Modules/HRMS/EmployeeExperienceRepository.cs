using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record EmployeeExperienceDraft(string Company, string? Designation, DateTime? From, DateTime? To, bool Current, string? Responsibilities);

internal sealed partial class EmployeeAdministrationRepository
{
    private const string ExperienceResource = "employee_experiences";

    internal async Task<(DataTable Rows, string Revision)> ReadExperienceAsync(int employee, CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        await AuthorizeAsync(db, tx, false, cancellation);
        string revision = await ReadQualificationRevisionAsync(db, tx, employee, false, cancellation);
        using var query = new NpgsqlCommand(@"SELECT ed.id,ed.company_name,ed.designation,ed.from_date::timestamp,ed.to_date::timestamp,ed.is_current,ed.responsibilities
            FROM public.employee_experiences ed WHERE ed.employee_id=@employee" + QualificationScope +
            " ORDER BY ed.from_date DESC NULLS LAST,ed.id DESC", db, tx);
        SetScope(query);
        query.Parameters.AddWithValue("resource", ExperienceResource);
        query.Parameters.AddWithValue("employee", employee);
        return (await ReadTableAsync(query, cancellation), revision);
    }

    internal async Task<int> SaveExperienceAsync(int employee, string revision, int? record, EmployeeExperienceDraft? draft,
        CancellationToken cancellation)
    {
        if (draft is null && !record.HasValue)
            throw new InvalidOperationException("Select an experience record to delete.");
        if (draft is not null)
        {
            draft = draft with { Company = Clean(draft.Company, 200) ?? "", Designation = Clean(draft.Designation, 150),
                Responsibilities = string.IsNullOrWhiteSpace(draft.Responsibilities) ? null : draft.Responsibilities?.Trim() };
            if (draft.Company.Length == 0)
                throw new InvalidOperationException("Enter a company name.");
            if (draft.From.HasValue && draft.To.HasValue && draft.To.Value.Date < draft.From.Value.Date)
                throw new InvalidOperationException("To date must be on or after from date.");
            if (draft.Responsibilities?.Any(c => char.IsControl(c) && c is not ('\r' or '\n' or '\t')) == true)
                throw new InvalidOperationException("Responsibilities contain unsupported characters.");
        }

        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await AuthorizeAsync(db, tx, true, cancellation);
        if (revision != await ReadQualificationRevisionAsync(db, tx, employee, true, cancellation))
            throw new InvalidOperationException("The employee profile changed. Refresh before saving experience.");
        await AuthorizeAsync(db, tx, true, cancellation);

        var before = record.HasValue ? await QualificationValuesAsync(db, tx, employee, record.Value, ExperienceResource, cancellation) : new();
        using var write = new NpgsqlCommand(draft is null
            ? "DELETE FROM public.employee_experiences ed WHERE ed.id=@record AND ed.employee_id=@employee" + QualificationScope + " RETURNING id"
            : record.HasValue
                ? @"UPDATE public.employee_experiences ed SET company_name=@company_name,designation=@designation,from_date=@from_date,
                    to_date=@to_date,is_current=@current,responsibilities=@responsibilities
                    WHERE ed.id=@record AND ed.employee_id=@employee" + QualificationScope + " RETURNING id"
                : @"INSERT INTO public.employee_experiences(employee_id,company_name,designation,from_date,to_date,is_current,responsibilities,last_drawn_currency)
                    VALUES(@employee,@company_name,@designation,@from_date,@to_date,@current,@responsibilities,'INR') RETURNING id", db, tx);
        SetScope(write);
        write.Parameters.AddWithValue("resource", ExperienceResource);
        write.Parameters.AddWithValue("employee", employee);
        write.Parameters.Add("record", NpgsqlDbType.Integer).Value = (object?)record ?? DBNull.Value;
        if (draft is not null)
        {
            AddText(write, "company_name", draft.Company);
            AddText(write, "designation", draft.Designation);
            AddText(write, "responsibilities", draft.Responsibilities);
            write.Parameters.Add("from_date", NpgsqlDbType.Date).Value = (object?)draft.From?.Date ?? DBNull.Value;
            write.Parameters.Add("to_date", NpgsqlDbType.Date).Value = (object?)draft.To?.Date ?? DBNull.Value;
            write.Parameters.AddWithValue("current", draft.Current);
        }
        int id = await write.ExecuteScalarAsync(cancellation) is int saved ? saved
            : throw new InvalidOperationException("The experience record is unavailable.");
        var after = draft is null ? new() : await QualificationValuesAsync(db, tx, employee, id, ExperienceResource, cancellation);
        await FinishQualificationAsync(db, tx, actor.Id, employee, id, record.HasValue, draft is null, ExperienceResource,
            before, after, cancellation);
        await tx.CommitAsync(cancellation);
        return id;
    }
}

