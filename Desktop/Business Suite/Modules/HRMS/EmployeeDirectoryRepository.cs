using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record EmployeeDirectoryPage(DataTable Employees, long Total);

internal sealed class EmployeeDirectoryRepository(DesktopDatabaseSettings settings)
{
    internal const int PageSize = 24;

    internal Task<DataTable> ListAsync(string search, CancellationToken cancellation, bool export = false) =>
        ListFilteredAsync(search, "", false, cancellation, export);

    internal async Task<DataTable> ListFilteredAsync(string search, string skill, bool teamOnly,
        CancellationToken cancellation, bool export = false) =>
        (await ReadAsync(search, skill, teamOnly, 0, export ? 5000 : 10000,
            false, cancellation, export)).Employees;

    internal Task<EmployeeDirectoryPage> ListPageAsync(string search, string skill, bool teamOnly,
        int pageIndex, CancellationToken cancellation) =>
        ReadAsync(search, skill, teamOnly, (long)pageIndex * PageSize, PageSize,
            true, cancellation, false);

    private async Task<EmployeeDirectoryPage> ReadAsync(string search, string skill, bool teamOnly,
        long offset, int limit, bool includeTotal, CancellationToken cancellation, bool export)
    {
        if (settings.BranchId is not int branch)
            throw new InvalidOperationException("Choose a branch before opening the Employee Directory.");

        using var connection = new NpgsqlConnection(settings.ConnectionString);
        await connection.OpenAsync(cancellation);
        using var transaction = connection.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await settings.RequireActorAsync(connection, transaction, cancellation);
        if (teamOnly)
        {
            using var employee = new NpgsqlCommand(@"SELECT 1 FROM public.employees e
                JOIN public.branches b ON b.id=e.branch_id AND b.company_id=@company
                WHERE e.user_id=@actor AND e.deleted_at IS NULL", connection, transaction);
            employee.Parameters.AddWithValue("company", settings.OrganizationId);
            employee.Parameters.AddWithValue("actor", actor.Id);
            if (await employee.ExecuteScalarAsync(cancellation) is null)
                throw new InvalidOperationException("No employee profile is linked to this user.");
        }

        skill = skill.Trim();
        string skillFilter = skill.Length == 0 ? "" : @"
                AND (strpos(lower(COALESCE(e.skills_tags,'')),lower(@skill))>0
                    OR EXISTS (SELECT 1 FROM public.employee_skills skill WHERE skill.employee_id=e.id
                        AND strpos(lower(skill.skill_name),lower(@skill))>0))";
        string totalColumn = includeTotal ? ", count(*) OVER () AS directory_total" : "";
        using var command = new NpgsqlCommand($@"
            WITH viewer AS (
                SELECT e.id AS employee_id, e.reporting_manager_id, u.is_superuser,
                    replace(lower(COALESCE(r.name,'')), ' ', '_') AS role_name
                FROM public.users u
                LEFT JOIN public.roles r ON r.id=u.role_id
                LEFT JOIN public.employees e ON e.user_id=u.id AND e.deleted_at IS NULL
                    AND EXISTS (SELECT 1 FROM public.branches b WHERE b.id=e.branch_id AND b.company_id=@company)
                WHERE u.id=@actor
            )
            SELECT e.employee_id,
                COALESCE(NULLIF(e.preferred_display_name, ''), concat_ws(' ',e.first_name,e.last_name)) AS employee_name,
                COALESCE(d.name,'') AS department, COALESCE(j.name,'') AS designation,
                b.name AS branch, COALESCE(e.work_location,'') AS work_location, e.status,
                CASE WHEN contact.visible THEN COALESCE(e.work_email,e.personal_email,'')
                     WHEN COALESCE(e.work_email,e.personal_email) IS NOT NULL THEN 'Hidden by privacy setting'
                     ELSE '' END AS email,
                CASE WHEN contact.visible THEN concat_ws(' ', e.phone_number_country_code,e.phone_number)
                     WHEN e.phone_number IS NOT NULL THEN 'Hidden by privacy setting'
                     ELSE '' END AS phone{totalColumn}
            FROM public.employees e
            CROSS JOIN viewer
            CROSS JOIN LATERAL (SELECT viewer.is_superuser
                OR viewer.role_name IN ('admin','super_admin','hr','hr_admin','hr_manager','ceo','founder','director','executive')
                OR COALESCE(e.directory_visibility,'public')='public'
                OR (e.directory_visibility='team' AND (e.id=viewer.employee_id OR e.reporting_manager_id=viewer.employee_id
                    OR e.reporting_manager_id=viewer.reporting_manager_id)) AS visible) contact
            JOIN public.branches b ON b.id=e.branch_id AND b.company_id=@company
            LEFT JOIN public.departments d ON d.id=e.department_id AND d.branch_id=b.id
            LEFT JOIN public.designations j ON j.id=e.designation_id AND j.department_id=d.id
            WHERE b.id=@branch AND e.deleted_at IS NULL AND e.status IN ('Active','Probation','On Leave')
                AND e.directory_visibility IS DISTINCT FROM 'hidden'
                AND (NOT @team_only OR e.reporting_manager_id=viewer.employee_id)
                {skillFilter}
                AND (@search='' OR strpos(lower(e.employee_id),lower(@search))>0
                    OR strpos(lower(concat_ws(' ',e.first_name,e.last_name)),lower(@search))>0
                    OR strpos(lower(COALESCE(e.preferred_display_name,'')),lower(@search))>0
                    OR strpos(lower(COALESCE(e.skills_tags,'')),lower(@search))>0
                    OR (contact.visible AND (strpos(lower(COALESCE(e.work_email,'')),lower(@search))>0
                        OR strpos(lower(COALESCE(e.personal_email,'')),lower(@search))>0)))
            ORDER BY lower(e.first_name),lower(e.last_name),e.id LIMIT @limit OFFSET @offset", connection, transaction);
        command.Parameters.AddWithValue("company", settings.OrganizationId);
        command.Parameters.AddWithValue("branch", branch);
        command.Parameters.AddWithValue("actor", actor.Id);
        command.Parameters.AddWithValue("limit", limit);
        command.Parameters.AddWithValue("offset", offset);
        command.Parameters.AddWithValue("search", NpgsqlDbType.Text, search.Trim());
        if (skill.Length > 0)
            command.Parameters.AddWithValue("skill", NpgsqlDbType.Text, skill);
        command.Parameters.AddWithValue("team_only", teamOnly);

        var table = new DataTable();
        long total = 0;
        using (var reader = await command.ExecuteReaderAsync(cancellation))
        {
            int fieldCount = reader.FieldCount - (includeTotal ? 1 : 0);
            for (int index = 0; index < fieldCount; index++)
                table.Columns.Add(reader.GetName(index), typeof(string));
            while (await reader.ReadAsync(cancellation))
            {
                if (includeTotal)
                    total = reader.GetInt64(fieldCount);
                var values = new object[fieldCount];
                reader.GetValues(values);
                table.Rows.Add(values);
            }
        }
        if (export)
        {
            using var audit = new NpgsqlCommand(@"INSERT INTO public.audit_logs
                (organization_id, user_id, method, endpoint, status_code, entity_type, action, description,
                 actor_authenticated, module)
                VALUES (@company, @actor, 'GET', 'desktop/employees/directory/export', 200,
                 'employee_directory', 'EXPORT', @description, true, 'hrms')", connection, transaction);
            audit.Parameters.AddWithValue("company", settings.OrganizationId);
            audit.Parameters.AddWithValue("actor", actor.Id);
            audit.Parameters.AddWithValue("description", $"Exported {table.Rows.Count} directory rows with role masking");
            await audit.ExecuteNonQueryAsync(cancellation);
            await transaction.CommitAsync(cancellation);
        }
        return new(table, includeTotal ? total : table.Rows.Count);
    }
}
