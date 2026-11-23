using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record DesktopModuleGrant(string Scope, string LegacyRole, bool IsLegacy);

internal static class DesktopModuleAccess
{
    private sealed record Grant(bool Enabled, string Scope, string[] Permissions, string[] Actions);

    internal static async Task<DesktopModuleGrant> RequireAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        int company, int branch, DesktopActor actor, string module, string action, params string[] acceptedPermissions)
    {
        const string sql = @"
            SELECT p.status, p.grants::text, b.module_grants::text, coalesce(r.name, ''),
                EXISTS (SELECT 1 FROM public.employees e WHERE e.user_id = u.id
                        AND e.deleted_at IS NULL AND lower(e.employment_type) = 'intern'),
                ARRAY(SELECT q.name FROM public.role_permissions qrole
                      JOIN public.permissions q ON q.id = qrole.permission_id
                      WHERE qrole.role_id = u.role_id),
                EXISTS (SELECT 1 FROM public.bos_enabled_modules m
                        WHERE m.company_id = @company AND m.module_key = @module AND NOT m.enabled),
                EXISTS (SELECT 1 FROM public.suite_service_policies g WHERE g.organization_id = @company
                        AND g.kind = 'governance' AND g.values_json->>'module' = @module
                        AND g.values_json->>'classification' = 'restricted'
                        AND NOT coalesce(g.values_json::jsonb->'allowedRoles' @> jsonb_build_array(u.role_id), false))
            FROM public.users u
            LEFT JOIN public.roles r ON r.id = u.role_id
            LEFT JOIN public.suite_access_policies p ON p.user_id = u.id AND p.company_id = @company
            LEFT JOIN public.suite_branch_grants b ON b.user_id = u.id AND b.company_id = @company AND b.branch_id = @branch
            WHERE u.id = @actor AND u.is_active";
        using var command = new NpgsqlCommand(sql, db, tx);
        command.Parameters.AddWithValue("company", NpgsqlDbType.Integer, company);
        command.Parameters.AddWithValue("branch", NpgsqlDbType.Integer, branch);
        command.Parameters.AddWithValue("actor", NpgsqlDbType.Integer, actor.Id);
        command.Parameters.AddWithValue("module", NpgsqlDbType.Text, module);
        string? companyGrants;
        string? branchGrants;
        string legacyRole;
        string[] legacyPermissions;
        using (var row = await command.ExecuteReaderAsync())
        {
            if (!await row.ReadAsync() || (!row.IsDBNull(0) && row.GetString(0) != "active") ||
                row.GetBoolean(6) || (row.GetBoolean(7) && !actor.IsSuperuser))
                throw Denied();
            legacyRole = row.GetString(3).ToLowerInvariant().Replace(' ', '_');
            if (!actor.IsSuperuser && (legacyRole == "intern" || row.GetBoolean(4)))
                throw Denied();
            legacyPermissions = row.GetFieldValue<string[]>(5);
            companyGrants = row.IsDBNull(1) ? null : row.GetString(1);
            branchGrants = row.IsDBNull(2) ? null : row.GetString(2);
        }

        await CheckSubscriptionAsync(db, tx, company, module);
        if (actor.IsSuperuser)
            return new DesktopModuleGrant("organization", legacyRole, false);
        Grant grant = companyGrants is null
            ? new Grant(true, "own", legacyPermissions,
                legacyPermissions.Any(p => p.StartsWith(module + "_", StringComparison.Ordinal) &&
                    (p.Contains("manage") || p.Contains("admin")))
                    ? new[] { "view", "create", "edit", "delete", "approve" } : new[] { "view" })
            : await ResolveAsync(db, tx, company, module, companyGrants);
        if (branchGrants is not null)
        {
            Grant restriction = await ResolveAsync(db, tx, company, module, branchGrants);
            string scope = (grant.Scope, restriction.Scope) switch
            {
                (var upper, var lower) when upper == lower => lower,
                ("organization", var lower) => lower,
                (var upper, "organization") => upper,
                ("branch" or "department" or "team", "own") => "own",
                _ => "unsupported"
            };
            grant = new Grant(grant.Enabled && restriction.Enabled, scope,
                grant.Permissions.Intersect(restriction.Permissions).ToArray(),
                grant.Actions.Intersect(restriction.Actions).ToArray());
        }
        bool legacy = companyGrants is null && branchGrants is null;
        string[] selected = grant.Permissions.Intersect(acceptedPermissions).ToArray();
        if (!grant.Enabled || (!legacy && !grant.Actions.Contains(action)) || selected.Length == 0 ||
            !await PermissionExistsAsync(db, tx, selected))
            throw Denied();
        if (grant.Scope is not ("organization" or "own" or "assigned" or "branch" or "department" or "team"))
            throw new UnauthorizedAccessException("Your company and branch record scopes do not overlap.");
        return new DesktopModuleGrant(legacy ? "organization" : grant.Scope, legacyRole, legacy);
    }

    private static async Task<Grant> ResolveAsync(NpgsqlConnection db, NpgsqlTransaction tx, int company, string module, string json)
    {
        using var document = JsonDocument.Parse(json);
        if (!ObjectProperty(document.RootElement, module, out var grant) ||
            !grant.TryGetProperty("enabled", out var enabled) || enabled.ValueKind != JsonValueKind.True)
            return new Grant(false, "own", Array.Empty<string>(), Array.Empty<string>());
        string? scope = StringProperty(grant, "scope");
        if (!grant.TryGetProperty("roleId", out var id) || id.ValueKind == JsonValueKind.Null)
            return new Grant(true, scope ?? "own", Names(grant, "permissions"), Names(grant, "actions"));
        if (id.ValueKind != JsonValueKind.Number || !id.TryGetInt32(out int roleId))
            throw Denied();
        using var command = new NpgsqlCommand(@"
            SELECT scope, json_build_object('permissions', permissions, 'actions', actions)::text
            FROM public.suite_access_roles
            WHERE id = @role AND company_id = @company AND module_key = @module AND active", db, tx);
        command.Parameters.AddWithValue("role", NpgsqlDbType.Integer, roleId);
        command.Parameters.AddWithValue("module", NpgsqlDbType.Text, module);
        command.Parameters.AddWithValue("company", NpgsqlDbType.Integer, company);
        using var row = await command.ExecuteReaderAsync();
        if (!await row.ReadAsync())
            throw Denied();
        using var role = JsonDocument.Parse(row.GetString(1));
        return new Grant(true, scope ?? row.GetString(0), Names(role.RootElement, "permissions"), Names(role.RootElement, "actions"));
    }

    private static async Task CheckSubscriptionAsync(NpgsqlConnection db, NpgsqlTransaction tx, int company, string module)
    {
        using var command = new NpgsqlCommand(@"
            SELECT s.status, s.config_json::text, p.config_json::text, p.id
            FROM public.tenant_subscriptions s
            LEFT JOIN public.tenant_subscription_plans p ON p.id = s.plan_id
            WHERE s.company_id = @company", db, tx);
        command.Parameters.AddWithValue("company", NpgsqlDbType.Integer, company);
        using var row = await command.ExecuteReaderAsync();
        if (!await row.ReadAsync())
            return;
        if (row.IsDBNull(3))
            throw Denied();
        using var subscription = JsonDocument.Parse(row.IsDBNull(1) ? "{}" : row.GetString(1));
        using var plan = JsonDocument.Parse(row.IsDBNull(2) ? "{}" : row.GetString(2));
        var settings = new Dictionary<string, JsonElement>();
        foreach (var source in new[] { plan.RootElement, subscription.RootElement })
            if (source.ValueKind == JsonValueKind.Object)
                foreach (var property in source.EnumerateObject())
                    settings[property.Name] = property.Value;
        if (settings.TryGetValue("scheduled_change", out var scheduled) &&
            scheduled.ValueKind is not (JsonValueKind.Null or JsonValueKind.False))
            throw new UnauthorizedAccessException("Review the scheduled company subscription change before using this workspace.");
        if (!settings.TryGetValue("enforce", out var enforce) || enforce.ValueKind == JsonValueKind.False)
            return;
        if (row.GetString(0) == "suspended" ||
            (settings.TryGetValue("expiry_policy", out var policy) && policy.ValueKind == JsonValueKind.String &&
             policy.GetString() == "restrict" && settings.TryGetValue("grace_until", out var grace) &&
             grace.ValueKind != JsonValueKind.Null &&
             (grace.ValueKind != JsonValueKind.String || !grace.TryGetDateTimeOffset(out var until) || until < DateTimeOffset.UtcNow)) ||
            !settings.TryGetValue("modules", out var modules) || modules.ValueKind != JsonValueKind.Array ||
            !modules.EnumerateArray().Any(item => item.ValueKind == JsonValueKind.String && item.GetString() == module))
            throw Denied();
    }

    private static async Task<bool> PermissionExistsAsync(NpgsqlConnection db, NpgsqlTransaction tx, string[] permissions)
    {
        using var command = new NpgsqlCommand("SELECT EXISTS (SELECT 1 FROM public.permissions WHERE name = ANY(@permissions))", db, tx);
        command.Parameters.AddWithValue("permissions", NpgsqlDbType.Array | NpgsqlDbType.Text, permissions);
        return (bool)(await command.ExecuteScalarAsync())!;
    }

    private static string[] Names(JsonElement value, string name) =>
        value.TryGetProperty(name, out var names) && names.ValueKind == JsonValueKind.Array
            ? names.EnumerateArray().Where(item => item.ValueKind == JsonValueKind.String).Select(item => item.GetString()!).ToArray()
            : Array.Empty<string>();

    private static string? StringProperty(JsonElement value, string name) =>
        value.TryGetProperty(name, out var field) && field.ValueKind == JsonValueKind.String ? field.GetString() : null;

    private static bool ObjectProperty(JsonElement value, string name, out JsonElement field)
    {
        field = default;
        return value.ValueKind == JsonValueKind.Object && value.TryGetProperty(name, out field) &&
            field.ValueKind == JsonValueKind.Object;
    }

    private static UnauthorizedAccessException Denied() =>
        new UnauthorizedAccessException("Your current company and branch access does not authorize this operation.");
}
