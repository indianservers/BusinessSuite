using System.Data;
using System.Globalization;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record EmployeeEducationDraft(string Degree, string? Specialization, string? Institution,
    string? Board, int? Year, decimal? Result);

internal sealed partial class EmployeeAdministrationRepository
{
    private const string QualificationScope = @" AND NOT EXISTS (
        SELECT 1 FROM public.suite_branch_ownership o
        WHERE o.resource_table=@resource AND o.resource_key=ed.id::text
          AND (o.company_id<>@company OR o.branch_id<>@branch))";

    internal async Task<(DataTable Rows, string Revision)> ReadEducationAsync(int employee, CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        await AuthorizeAsync(db, tx, false, cancellation);
        string revision = await ReadQualificationRevisionAsync(db, tx, employee, false, cancellation);
        using var query = new NpgsqlCommand(@"SELECT ed.id,ed.degree,ed.specialization,ed.institution,
            ed.board_university,ed.pass_year,ed.percentage_cgpa FROM public.employee_educations ed
            WHERE ed.employee_id=@employee" + QualificationScope + " ORDER BY ed.pass_year DESC NULLS LAST,ed.id DESC", db, tx);
        SetScope(query);
        query.Parameters.AddWithValue("resource", "employee_educations");
        query.Parameters.AddWithValue("employee", employee);
        return (await ReadTableAsync(query, cancellation), revision);
    }

    internal async Task<int> SaveEducationAsync(int employee, string revision, int? record, EmployeeEducationDraft? draft,
        CancellationToken cancellation)
    {
        if (draft is null && !record.HasValue)
            throw new InvalidOperationException("Select an education record to delete.");
        if (draft is not null)
        {
            draft = draft with { Degree = Clean(draft.Degree, 100) ?? "", Specialization = Clean(draft.Specialization, 150),
                Institution = Clean(draft.Institution, 200), Board = Clean(draft.Board, 200) };
            if (draft.Degree.Length == 0 || draft.Year is < 1900 or > 2200 || draft.Result is < 0 or > 100
                || (draft.Result.HasValue && decimal.Round(draft.Result.Value, 2) != draft.Result.Value))
                throw new InvalidOperationException("Enter a degree, a pass year from 1900 to 2200, and a result from 0 to 100 with up to two decimal places.");
        }

        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await AuthorizeAsync(db, tx, true, cancellation);
        if (revision != await ReadQualificationRevisionAsync(db, tx, employee, true, cancellation))
            throw new InvalidOperationException("The employee profile changed. Refresh before saving education.");
        await AuthorizeAsync(db, tx, true, cancellation);

        var before = record.HasValue ? await QualificationValuesAsync(db, tx, employee, record.Value, "employee_educations", cancellation) : new();
        using var write = new NpgsqlCommand(draft is null
            ? "DELETE FROM public.employee_educations ed WHERE ed.id=@record AND ed.employee_id=@employee" + QualificationScope + " RETURNING id"
            : record.HasValue
                ? @"UPDATE public.employee_educations ed SET degree=@degree,specialization=@specialization,institution=@institution,
                    board_university=@board,pass_year=@year,percentage_cgpa=@result WHERE ed.id=@record AND ed.employee_id=@employee"
                    + QualificationScope + " RETURNING id"
                : @"INSERT INTO public.employee_educations(employee_id,degree,specialization,institution,board_university,
                    pass_year,percentage_cgpa,education_mode,is_highest_qualification)
                    VALUES(@employee,@degree,@specialization,@institution,@board,@year,@result,'Regular',false) RETURNING id", db, tx);
        SetScope(write);
        write.Parameters.AddWithValue("resource", "employee_educations");
        write.Parameters.AddWithValue("employee", employee);
        write.Parameters.Add("record", NpgsqlDbType.Integer).Value = (object?)record ?? DBNull.Value;
        if (draft is not null)
        {
            AddText(write, "degree", draft.Degree);
            AddText(write, "specialization", draft.Specialization);
            AddText(write, "institution", draft.Institution);
            AddText(write, "board", draft.Board);
            write.Parameters.Add("year", NpgsqlDbType.Integer).Value = (object?)draft.Year ?? DBNull.Value;
            write.Parameters.Add("result", NpgsqlDbType.Numeric).Value = (object?)draft.Result ?? DBNull.Value;
        }
        int id = await write.ExecuteScalarAsync(cancellation) is int saved ? saved
            : throw new InvalidOperationException("The qualification record is unavailable.");
        var after = draft is null ? new() : await QualificationValuesAsync(db, tx, employee, id, "employee_educations", cancellation);
        await FinishQualificationAsync(db, tx, actor.Id, employee, id, record.HasValue, draft is null, "employee_educations",
            before, after, cancellation);
        await tx.CommitAsync(cancellation);
        return id;
    }

    private static string? Clean(string? value, int length)
    {
        value = value?.Trim();
        if (value?.Length > length || value?.Any(char.IsControl) == true)
            throw new InvalidOperationException($"Profile text cannot exceed {length} characters or contain control characters.");
        return string.IsNullOrEmpty(value) ? null : value;
    }

    private async Task<Dictionary<string, string?>> QualificationValuesAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        int employee, int record, string resource, CancellationToken cancellation)
    {
        string table = resource switch
        {
            "employee_educations" => "public.employee_educations",
            SkillsResource => "public.employee_skills",
            ExperienceResource => "public.employee_experiences",
            CertificationResource => "public.employee_certifications",
            DocumentResource => "public.employee_documents",
            _ => throw new ArgumentOutOfRangeException(nameof(resource))
        };
        using var query = new NpgsqlCommand(@"SELECT f.key,f.value FROM " + table + @" ed
            CROSS JOIN LATERAL jsonb_each_text(to_jsonb(ed)-'id'-'employee_id'-'created_at') f
            WHERE ed.id=@record AND ed.employee_id=@employee" + QualificationScope, db, tx);
        SetScope(query);
        query.Parameters.AddWithValue("resource", resource);
        query.Parameters.AddWithValue("employee", employee);
        query.Parameters.AddWithValue("record", record);
        var result = new Dictionary<string, string?>();
        using var rows = await query.ExecuteReaderAsync(cancellation);
        while (await rows.ReadAsync(cancellation))
            result.Add(rows.GetString(0), rows.IsDBNull(1) ? null : rows.GetString(1));
        if (result.Count == 0)
            throw new InvalidOperationException("The qualification record is unavailable.");
        return result;
    }

    private async Task FinishQualificationAsync(NpgsqlConnection db, NpgsqlTransaction tx, int actor, int employee, int id,
        bool existing, bool deleted, string resource, Dictionary<string, string?> before, Dictionary<string, string?> after,
        CancellationToken cancellation)
    {
        if (!existing)
            await RecordOwnershipAsync(db, tx, resource, id, cancellation);
        if (deleted)
        {
            using var clear = new NpgsqlCommand(@"DELETE FROM public.suite_branch_ownership WHERE
                resource_table=@resource AND resource_key=@key AND company_id=@company AND branch_id=@branch", db, tx);
            SetScope(clear);
            clear.Parameters.AddWithValue("resource", resource);
            clear.Parameters.AddWithValue("key", id.ToString(CultureInfo.InvariantCulture));
            await clear.ExecuteNonQueryAsync(cancellation);
        }

        string action = deleted ? "deleted" : existing ? "updated" : "created";
        foreach (var field in before.Keys.Union(after.Keys).OrderBy(key => key, StringComparer.Ordinal))
        {
            before.TryGetValue(field, out var oldValue);
            after.TryGetValue(field, out var newValue);
            if (oldValue != newValue)
                await RecordFieldAsync(db, tx, actor, employee, field, oldValue, newValue, cancellation, resource, id, action);
        }
        using var touch = new NpgsqlCommand("UPDATE public.employees SET updated_at=clock_timestamp() WHERE id=@employee", db, tx);
        touch.Parameters.AddWithValue("employee", employee);
        await touch.ExecuteNonQueryAsync(cancellation);
    }

    private async Task<string> ReadQualificationRevisionAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        int employee, bool write, CancellationToken cancellation)
    {
        using var parent = new NpgsqlCommand("SELECT e.xmin::text" + ScopedEmployees + " AND e.id=@employee" +
            (write ? " FOR UPDATE OF e" : ""), db, tx);
        SetScope(parent);
        parent.Parameters.AddWithValue("employee", employee);
        if (await parent.ExecuteScalarAsync(cancellation) is not string employeeRevision)
            throw new InvalidOperationException("The employee profile is unavailable.");
        using var records = new NpgsqlCommand(@"
            SELECT md5(concat_ws('|',@revision,
                (SELECT string_agg(id::text||':'||xmin::text,',' ORDER BY id) FROM public.employee_educations WHERE employee_id=@employee),
                (SELECT string_agg(id::text||':'||xmin::text,',' ORDER BY id) FROM public.employee_experiences WHERE employee_id=@employee),
                (SELECT string_agg(id::text||':'||xmin::text,',' ORDER BY id) FROM public.employee_skills WHERE employee_id=@employee),
                (SELECT string_agg(id::text||':'||xmin::text,',' ORDER BY id) FROM public.employee_certifications WHERE employee_id=@employee),
                (SELECT string_agg(id::text||':'||xmin::text,',' ORDER BY id) FROM public.employee_documents WHERE employee_id=@employee)))", db, tx);
        records.Parameters.AddWithValue("employee", employee);
        records.Parameters.AddWithValue("revision", employeeRevision);
        return (string)(await records.ExecuteScalarAsync(cancellation))!;
    }
}
