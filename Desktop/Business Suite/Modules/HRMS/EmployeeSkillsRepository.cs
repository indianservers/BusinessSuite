using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record EmployeeSkillDraft(string Name, string? Proficiency, decimal? Years);

internal sealed partial class EmployeeAdministrationRepository
{
    private const string SkillsResource = "employee_skills";

    internal async Task<(DataTable Rows, string Revision)> ReadSkillsAsync(int employee, CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        await AuthorizeAsync(db, tx, false, cancellation);
        string revision = await ReadQualificationRevisionAsync(db, tx, employee, false, cancellation);
        using var query = new NpgsqlCommand(@"SELECT ed.id,ed.skill_name,ed.proficiency,ed.years_experience
            FROM public.employee_skills ed WHERE ed.employee_id=@employee" + QualificationScope +
            " ORDER BY lower(ed.skill_name),ed.id", db, tx);
        SetScope(query);
        query.Parameters.AddWithValue("resource", SkillsResource);
        query.Parameters.AddWithValue("employee", employee);
        return (await ReadTableAsync(query, cancellation), revision);
    }

    internal async Task<int> SaveSkillAsync(int employee, string revision, int? record, EmployeeSkillDraft? draft,
        CancellationToken cancellation)
    {
        if (draft is null && !record.HasValue)
            throw new InvalidOperationException("Select a skill to delete.");
        if (draft is not null)
        {
            draft = draft with { Name = Clean(draft.Name, 100) ?? "", Proficiency = Clean(draft.Proficiency, 30) };
            if (draft.Name.Length == 0)
                throw new InvalidOperationException("Enter a skill name.");
            if (draft.Years is < 0 or > 999.9m || (draft.Years.HasValue && decimal.Round(draft.Years.Value, 1) != draft.Years.Value))
                throw new InvalidOperationException("Enter years of experience from 0 to 999.9 with up to one decimal place.");
        }

        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await AuthorizeAsync(db, tx, true, cancellation);
        if (revision != await ReadQualificationRevisionAsync(db, tx, employee, true, cancellation))
            throw new InvalidOperationException("The employee profile changed. Refresh before saving skills.");
        await AuthorizeAsync(db, tx, true, cancellation);

        var before = record.HasValue ? await QualificationValuesAsync(db, tx, employee, record.Value, SkillsResource, cancellation) : new();
        using var write = new NpgsqlCommand(draft is null
            ? "DELETE FROM public.employee_skills ed WHERE ed.id=@record AND ed.employee_id=@employee" + QualificationScope + " RETURNING id"
            : record.HasValue
                ? @"UPDATE public.employee_skills ed SET skill_name=@name,proficiency=@proficiency,years_experience=@years
                    WHERE ed.id=@record AND ed.employee_id=@employee" + QualificationScope + " RETURNING id"
                : @"INSERT INTO public.employee_skills(employee_id,skill_name,proficiency,years_experience)
                    VALUES(@employee,@name,@proficiency,@years) RETURNING id", db, tx);
        SetScope(write);
        write.Parameters.AddWithValue("resource", SkillsResource);
        write.Parameters.AddWithValue("employee", employee);
        write.Parameters.Add("record", NpgsqlDbType.Integer).Value = (object?)record ?? DBNull.Value;
        if (draft is not null)
        {
            AddText(write, "name", draft.Name);
            AddText(write, "proficiency", draft.Proficiency);
            write.Parameters.Add("years", NpgsqlDbType.Numeric).Value = (object?)draft.Years ?? DBNull.Value;
        }
        int id = await write.ExecuteScalarAsync(cancellation) is int saved ? saved
            : throw new InvalidOperationException("The skill is unavailable.");
        var after = draft is null ? new() : await QualificationValuesAsync(db, tx, employee, id, SkillsResource, cancellation);
        await FinishQualificationAsync(db, tx, actor.Id, employee, id, record.HasValue, draft is null, SkillsResource,
            before, after, cancellation);
        await tx.CommitAsync(cancellation);
        return id;
    }
}
