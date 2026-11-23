using System.Data;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record EmployeeAdministrationDraft(string? DisplayName, string? WorkLocation,
    string? OfficeExtension, string? DeskCode, string? DirectoryVisibility);

internal sealed partial class EmployeeAdministrationRepository(DesktopDatabaseSettings settings)
{
    private const string ScopedEmployees = @"
        FROM public.employees e
        JOIN public.branches b ON b.id = e.branch_id AND b.company_id = @company
        WHERE e.deleted_at IS NULL AND e.branch_id = @branch
          AND EXISTS (SELECT 1 FROM public.suite_branch_ownership o
                      WHERE o.resource_table = 'employees' AND o.resource_key = e.id::text
                        AND o.company_id = @company AND o.branch_id = @branch)";

    internal async Task<DataTable> ListAsync(string search, CancellationToken cancellation)
    {
        using var connection = new NpgsqlConnection(settings.ConnectionString);
        await connection.OpenAsync(cancellation);
        using var transaction = connection.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await AuthorizeAsync(connection, transaction, false, cancellation);
        bool canArchive = false;
        if (actor.CanWriteBranch)
        {
            try
            {
                var grant = await DesktopModuleAccess.RequireAsync(connection, transaction,
                    settings.OrganizationId, settings.BranchId!.Value, actor, "hrms", "delete", "employee_delete");
                canArchive = grant.Scope is "organization" or "branch";
            }
            catch (UnauthorizedAccessException) { }
        }
        using var query = new NpgsqlCommand(@"
            SELECT e.id, e.xmin::text AS revision, e.employee_id,
                   concat_ws(' ', e.first_name, e.last_name) AS employee_name,
                   e.preferred_display_name, e.work_location, e.office_extension,
                   e.desk_code, e.directory_visibility, e.status,
                   e.user_id IS NOT NULL AS linked_login, @writable AS can_write, @archive AS can_archive,
                   coalesce((SELECT u.is_active FROM public.users u WHERE u.id = e.user_id), false) AS login_active,
                   concat(e.xmin::text, ':', (SELECT u.xmin::text FROM public.users u WHERE u.id = e.user_id))
                       AS employment_revision" + ScopedEmployees + @"
              AND (@search = '' OR strpos(lower(e.employee_id), lower(@search)) > 0
                   OR strpos(lower(concat_ws(' ', e.first_name, e.last_name)),lower(@search)) > 0
                   OR strpos(lower(e.preferred_display_name), lower(@search)) > 0)
            ORDER BY lower(e.first_name), lower(e.last_name), e.id LIMIT 2000", connection, transaction);
        SetScope(query);
        query.Parameters.AddWithValue("archive", canArchive);
        query.Parameters.AddWithValue("search", search.Trim());
        query.Parameters.AddWithValue("writable", actor.CanWriteBranch);
        return await ReadTableAsync(query, cancellation);
    }

    private static async Task<DataTable> ReadTableAsync(NpgsqlCommand query, CancellationToken cancellation)
    {
        using var reader = await query.ExecuteReaderAsync(cancellation);
        var table = new DataTable();
        for (int index = 0; index < reader.FieldCount; index++)
            table.Columns.Add(reader.GetName(index), reader.GetFieldType(index));
        while (await reader.ReadAsync(cancellation))
        {
            var values = new object[reader.FieldCount];
            reader.GetValues(values);
            table.Rows.Add(values);
        }
        return table;
    }

    internal async Task SaveAsync(int id, string revision, EmployeeAdministrationDraft draft, CancellationToken cancellation)
    {
        using var connection = new NpgsqlConnection(settings.ConnectionString);
        await connection.OpenAsync(cancellation);
        using var transaction = connection.BeginTransaction();
        var actor = await AuthorizeAsync(connection, transaction, true, cancellation);
        string?[] previous = new string?[5];
        using (var query = new NpgsqlCommand(@"
            SELECT e.preferred_display_name, e.work_location, e.office_extension, e.desk_code, e.directory_visibility" +
            ScopedEmployees + " AND e.id = @id AND e.xmin::text = @revision FOR UPDATE OF e", connection, transaction))
        {
            SetScope(query);
            query.Parameters.AddWithValue("id", id);
            query.Parameters.AddWithValue("revision", revision);
            using var row = await query.ExecuteReaderAsync(cancellation);
            if (!await row.ReadAsync(cancellation))
                throw new InvalidOperationException("The employee profile changed or is unavailable. Refresh before saving again.");
            for (int index = 0; index < previous.Length; index++)
                previous[index] = row.IsDBNull(index) ? null : row.GetString(index);
        }

        actor = await AuthorizeAsync(connection, transaction, true, cancellation);
        var display = ValidateChange(draft.DisplayName, previous[0], 500, "Display name");
        var location = ValidateChange(draft.WorkLocation, previous[1], 100, "Work location");
        var extension = ValidateChange(draft.OfficeExtension, previous[2], 60, "Office extension");
        var desk = ValidateChange(draft.DeskCode, previous[3], 100, "Desk code");
        var visibility = ValidateChange(draft.DirectoryVisibility, previous[4], 20, "Directory visibility");
        if (location != previous[1] && location is not (null or "Office" or "Remote" or "Hybrid" or "Field" or "On-Site"))
            throw new InvalidOperationException("Choose a valid work location.");
        if (visibility != previous[4] && visibility is not ("public" or "team" or "hidden"))
            throw new InvalidOperationException("Choose Public, Team or Hidden for directory visibility.");

        string[] fields = { "preferred_display_name", "work_location", "office_extension", "desk_code", "directory_visibility" };
        string?[] values = { display, location, extension, desk, visibility };
        var changes = Enumerable.Range(0, fields.Length).Where(index => previous[index] != values[index]).ToArray();
        if (changes.Length == 0)
            return;

        using (var update = new NpgsqlCommand(@"
            UPDATE public.employees SET preferred_display_name = @display, work_location = @location,
                office_extension = @extension, desk_code = @desk, directory_visibility = @visibility,
                updated_at = clock_timestamp()
            WHERE id = @id", connection, transaction))
        {
            update.Parameters.AddWithValue("id", id);
            AddText(update, "display", display);
            AddText(update, "location", location);
            AddText(update, "extension", extension);
            AddText(update, "desk", desk);
            AddText(update, "visibility", visibility);
            await update.ExecuteNonQueryAsync(cancellation);
        }

        foreach (int index in changes)
            await RecordFieldAsync(connection, transaction, actor.Id, id, fields[index], previous[index],
                values[index], cancellation);
        await RecordProfileEditAsync(connection, transaction, actor.Id, id,
            changes.Select(index => fields[index]).OrderBy(field => field, StringComparer.Ordinal).ToArray(), cancellation);
        await transaction.CommitAsync(cancellation);
    }

    private async Task<DesktopActor> AuthorizeAsync(NpgsqlConnection connection, NpgsqlTransaction transaction,
        bool write, CancellationToken cancellation)
    {
        int branch = settings.BranchId ?? throw new InvalidOperationException("Choose a branch before opening Employee Administration.");
        var actor = write
            ? await settings.VerifyWriteTargetAsync(connection, transaction, cancellation)
            : await settings.RequireActorAsync(connection, transaction, cancellation);
        var grant = await DesktopModuleAccess.RequireAsync(connection, transaction,
            settings.OrganizationId, branch, actor, "hrms", write ? "edit" : "view", "employee_update");
        if (grant.Scope is not ("organization" or "branch"))
            throw new UnauthorizedAccessException("Employee Administration requires organization or branch employee access.");
        return actor;
    }

    private async Task RecordFieldAsync(NpgsqlConnection connection, NpgsqlTransaction transaction, int actor,
        int employee, string field, string? before, string? after, CancellationToken cancellation,
        string entity = "employee", int? entityId = null, string action = "updated")
    {
        using var audit = new NpgsqlCommand(@"
            INSERT INTO public.field_audit_events (
                module, entity_type, entity_id, employee_id, field_name, action, old_value_masked, new_value_masked,
                old_value_hash, new_value_hash, old_value_plaintext, new_value_plaintext,
                is_sensitive, actor_user_id, reason, metadata_json)
            VALUES ('employee', @entity, @entity_id, @id, @field, @action, @before, @after, @before_hash, @after_hash,
                @before_plain, @after_plain, false, @actor, 'Desktop employee administration', '{}'::json)
            RETURNING id", connection, transaction);
        audit.Parameters.AddWithValue("id", employee);
        audit.Parameters.AddWithValue("actor", actor);
        audit.Parameters.AddWithValue("field", field);
        audit.Parameters.AddWithValue("entity", entity);
        audit.Parameters.AddWithValue("entity_id", entityId ?? employee);
        audit.Parameters.AddWithValue("action", action);
        bool keepPlaintext = field == "work_location";
        AddText(audit, "before", Mask(before, keepPlaintext));
        AddText(audit, "after", Mask(after, keepPlaintext));
        AddText(audit, "before_hash", Hash(before));
        AddText(audit, "after_hash", Hash(after));
        AddText(audit, "before_plain", keepPlaintext ? before : null);
        AddText(audit, "after_plain", keepPlaintext ? after : null);
        var auditId = (int)(await audit.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(connection, transaction, "field_audit_events", auditId, cancellation);
    }

    private async Task RecordProfileEditAsync(NpgsqlConnection connection, NpgsqlTransaction transaction, int actor,
        int employee, string[] fields, CancellationToken cancellation)
    {
        using var audit = new NpgsqlCommand(@"
            INSERT INTO public.audit_logs (organization_id, user_id, actor_email, actor_authenticated,
                method, endpoint, status_code, entity_type, entity_id, action, description, new_values, module)
            SELECT @company, id, left(email, 100), true, 'PUT', @endpoint, 200, 'employee', @id, 'PROFILE_EDIT',
                   @description, @changes, 'hrms' FROM public.users WHERE id = @actor
            RETURNING id", connection, transaction);
        audit.Parameters.AddWithValue("company", settings.OrganizationId);
        audit.Parameters.AddWithValue("id", employee);
        audit.Parameters.AddWithValue("actor", actor);
        audit.Parameters.AddWithValue("endpoint", $"desktop/employees/{employee}");
        audit.Parameters.AddWithValue("description", "Changed " + string.Join(", ", fields));
        audit.Parameters.AddWithValue("changes", JsonSerializer.Serialize(new { fields }));
        var auditId = (int)(await audit.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(connection, transaction, "audit_logs", auditId, cancellation);
    }

    private async Task RecordOwnershipAsync(NpgsqlConnection connection, NpgsqlTransaction transaction,
        string table, int id, CancellationToken cancellation)
    {
        using var command = new NpgsqlCommand(@"
            INSERT INTO public.suite_branch_ownership (resource_table, resource_key, company_id, branch_id, source)
            VALUES (@table, @id::text, @company, @branch, 'validated-write')", connection, transaction);
        SetScope(command);
        command.Parameters.AddWithValue("table", table);
        command.Parameters.AddWithValue("id", id);
        await command.ExecuteNonQueryAsync(cancellation);
    }

    private void SetScope(NpgsqlCommand command)
    {
        command.Parameters.AddWithValue("company", settings.OrganizationId);
        command.Parameters.AddWithValue("branch", settings.BranchId!.Value);
    }

    private static void AddText(NpgsqlCommand command, string name, string? value) =>
        command.Parameters.AddWithValue(name, NpgsqlDbType.Text, (object?)value ?? DBNull.Value);

    private static string? ValidateChange(string? value, string? current, int max, string label)
    {
        if (value is null || value == current)
            return value;
        var clean = value.Trim();
        if (clean.Length > max || clean.Any(char.IsControl))
            throw new InvalidOperationException($"{label} must contain at most {max} characters with no control characters.");
        return clean.Length == 0 ? null : clean;
    }

    private static string? Mask(string? value, bool keepPlaintext) =>
        string.IsNullOrEmpty(value) ? null : keepPlaintext ? value : "Changed (private)";

    private static string? Hash(string? value)
    {
        if (string.IsNullOrEmpty(value))
            return null;
        // Independent salts keep low-entropy masked fields from being guessable from audit data alone.
        using var random = RandomNumberGenerator.Create();
        using var hash = SHA256.Create();
        var salt = new byte[32];
        random.GetBytes(salt);
        return BitConverter.ToString(hash.ComputeHash(salt.Concat(Encoding.UTF8.GetBytes(value)).ToArray()))
            .Replace("-", "").ToLowerInvariant();
    }
}

