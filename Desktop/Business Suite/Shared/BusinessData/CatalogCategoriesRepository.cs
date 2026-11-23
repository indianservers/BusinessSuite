using System.Data;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record CatalogCategoryChild(string Id, string Name);
internal sealed record CatalogCategory(string Id, string Name, List<CatalogCategoryChild> Children);
internal sealed record CatalogTaxonomy(int Version, List<CatalogCategory> Categories, bool CanEdit = false);
internal sealed record CatalogCategoryUsage(int Id, string? Category, string[]? CategoryIds, string[]? Labels, bool PackOwned);

internal sealed class CatalogCategoriesRepository(DesktopDatabaseSettings settings)
{
    private static readonly JsonSerializerOptions Json = new() { PropertyNamingPolicy = JsonNamingPolicy.CamelCase };

    internal async Task<CatalogTaxonomy> LoadAsync(CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await settings.RequireActorAsync(db, tx, cancellation);
        await RequireAccessAsync(db, tx, actor, false);
        var taxonomy = await ReadSelectionAsync(db, tx, cancellation);
        if (!actor.CanWriteBranch)
            return taxonomy;
        try
        {
            await RequireAccessAsync(db, tx, actor, true);
            return taxonomy with { CanEdit = true };
        }
        catch (UnauthorizedAccessException)
        {
            return taxonomy;
        }
    }

    internal async Task<CatalogTaxonomy> SaveAsync(CatalogTaxonomy draft, CancellationToken cancellation)
    {
        Validate(draft.Categories);
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await settings.VerifyWriteTargetAsync(db, tx, cancellation);
        await RequireAccessAsync(db, tx, actor, true);

        using (var guard = ScopedCommand(db, tx, "SELECT id FROM public.companies WHERE id=@company FOR UPDATE"))
            await guard.ExecuteScalarAsync(cancellation);
        var products = await UsageAsync(db, tx, cancellation);
        var previous = await ReadAsync(db, tx, products, cancellation);
        if (previous.Version != draft.Version)
            throw new InvalidOperationException("Categories changed. Reload before saving.");

        var labels = draft.Categories
            .SelectMany(category => new[] { (category.Id, category.Name) }
                .Concat(category.Children.Select(child => (Id: child.Id, Name: $"{category.Name} > {child.Name}"))))
            .ToDictionary(pair => pair.Id, pair => pair.Name);
        var legacyNames = previous.Categories.ToDictionary(category => category.Name, category => category.Id);
        foreach (var product in products)
        {
            string[] ids = product.CategoryIds ?? (product.Category is not null
                && legacyNames.TryGetValue(product.Category, out string id) ? new[] { id } : Array.Empty<string>());
            if (ids.Length == 0)
                continue;
            if (ids.Any(categoryId => !labels.ContainsKey(categoryId)))
                throw new InvalidOperationException("Remove categories or subcategories from assigned items before deleting them.");
            string[] itemLabels = ids.Select(categoryId => labels[categoryId]).ToArray();
            if (product.Labels is not null && product.Labels.SequenceEqual(itemLabels))
                continue;
            if (product.PackOwned)
            {
                if (product.Labels is null && itemLabels.Length == 1 && product.Category == itemLabels[0])
                    continue;
                throw new InvalidOperationException("This change affects an offering managed by a business pack.");
            }

            using var update = ScopedCommand(db, tx, @"UPDATE public.srm_products
                SET metadata_json=(COALESCE(metadata_json::jsonb, '{}'::jsonb) ||
                    jsonb_build_object('catalog_category_ids', @ids::jsonb, 'catalog_categories', @labels::jsonb))::json,
                    category_name=split_part(@primary, ' > ',1), updated_at=now()
                WHERE id=@id AND COALESCE(organization_id,1)=@company AND deleted_at IS NULL");
            update.Parameters.AddWithValue("id", product.Id);
            update.Parameters.AddWithValue("ids", NpgsqlDbType.Jsonb, JsonSerializer.Serialize(ids));
            update.Parameters.AddWithValue("labels", NpgsqlDbType.Jsonb, JsonSerializer.Serialize(itemLabels));
            update.Parameters.AddWithValue("primary", itemLabels[0]);
            await update.ExecuteNonQueryAsync(cancellation);
        }

        int version = previous.Version + 1;
        using var save = ScopedCommand(db, tx, @"INSERT INTO public.suite_service_policies
            (scope_key, organization_id, module_key, kind, values_json, version, updated_by)
            VALUES ('catalog-categories:' || @company::text, @company, '*', 'catalog_categories', @value, @version, @actor)
            ON CONFLICT (scope_key) DO UPDATE
                SET values_json=EXCLUDED.values_json,version=EXCLUDED.version,updated_by=EXCLUDED.updated_by,updated_at=now()
                WHERE suite_service_policies.organization_id=@company AND suite_service_policies.kind='catalog_categories'");
        save.Parameters.AddWithValue("version", version);
        save.Parameters.AddWithValue("actor", actor.Id);
        save.Parameters.AddWithValue("value", NpgsqlDbType.Json, JsonSerializer.Serialize(new { categories = draft.Categories }, Json));
        if (await save.ExecuteNonQueryAsync(cancellation) != 1)
            throw new InvalidOperationException("The category policy belongs to a different scope.");
        await tx.CommitAsync(cancellation);
        return new(version, draft.Categories, true);
    }

    internal static string Normalize(string name) => Regex.Replace(name.Trim(), @"\s+", " ");

    private static void Validate(List<CatalogCategory> categories)
    {
        if (categories.Count > 100)
            throw new ArgumentException("Use up to 100 categories.");
        if (categories.Select(category => category.Name).Distinct(StringComparer.OrdinalIgnoreCase).Count() != categories.Count)
            throw new ArgumentException("Category names must be unique.");
        var ids = new HashSet<string>(StringComparer.Ordinal);
        foreach (var category in categories)
        {
            ValidateNode(category.Id, category.Name, ids);
            if (category.Children.Count > 100)
                throw new ArgumentException("Use up to 100 subcategories per category.");
            if (category.Children.Select(child => child.Name).Distinct(StringComparer.OrdinalIgnoreCase).Count() != category.Children.Count)
                throw new ArgumentException("Subcategory names must be unique within the category.");
            foreach (var child in category.Children)
                ValidateNode(child.Id, child.Name, ids);
        }
    }

    private static void ValidateNode(string id, string name, HashSet<string> ids)
    {
        if (!Regex.IsMatch(id, @"\A[A-Za-z0-9_-]{1,64}\z") || !ids.Add(id))
            throw new ArgumentException("Category and subcategory IDs must be valid and unique.");
        if (name != Normalize(name) || name.Length is < 1 or > 120 || name.Contains(">"))
            throw new ArgumentException("Use a category name between 1 and 120 characters without >.");
    }

    private async Task RequireAccessAsync(NpgsqlConnection db, NpgsqlTransaction tx, DesktopActor actor, bool write)
    {
        if (settings.BranchId is not int branch)
            throw new InvalidOperationException("Choose a branch before opening catalog categories.");
        var permissions = write ? new[] { "srm_manage", "srm_admin" } : new[] { "srm_view", "srm_manage", "srm_admin" };
        var grant = await DesktopModuleAccess.RequireAsync(db, tx, settings.OrganizationId, branch,
            actor, "srm", write ? "edit" : "view", permissions);
        if (grant.Scope != "organization")
            throw new UnauthorizedAccessException("Catalog categories require organization catalog access.");
    }

    internal async Task<CatalogTaxonomy> ReadSelectionAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        CancellationToken cancellation) =>
        await ReadAsync(db, tx, await UsageAsync(db, tx, cancellation), cancellation);

    private async Task<CatalogTaxonomy> ReadAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        List<CatalogCategoryUsage> products, CancellationToken cancellation)
    {
        using var command = ScopedCommand(db, tx, @"SELECT version, (values_json->'categories')::text
            FROM public.suite_service_policies WHERE scope_key='catalog-categories:' || @company::text
                AND organization_id=@company AND kind='catalog_categories'");
        using var reader = await command.ExecuteReaderAsync(cancellation);
        int version = 0;
        var categories = new List<CatalogCategory>();
        if (await reader.ReadAsync(cancellation))
        {
            version = reader.GetInt32(0);
            if (!reader.IsDBNull(1))
                categories = JsonSerializer.Deserialize<List<CatalogCategory>>(reader.GetString(1), Json) ?? categories;
        }
        var names = new HashSet<string>(categories.Select(category => category.Name), StringComparer.Ordinal);
        foreach (var product in products)
            if (!string.IsNullOrEmpty(product.Category) && names.Add(product.Category!))
                categories.Add(new(LegacyId(product.Category!), product.Category!, new()));
        return new(version, categories);
    }

    private async Task<List<CatalogCategoryUsage>> UsageAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        CancellationToken cancellation)
    {
        using var command = ScopedCommand(db, tx, @"SELECT p.id,p.category_name,
            (p.metadata_json->'catalog_category_ids')::text,(p.metadata_json->'catalog_categories')::text,
            EXISTS (SELECT 1 FROM public.business_pack_record_ownership r WHERE r.company_id=@company
                AND r.resource_table='srm_products' AND r.resource_key=p.id::text)
            FROM public.srm_products p WHERE COALESCE(p.organization_id,1)=@company AND p.deleted_at IS NULL
            ORDER BY p.id");
        using var reader = await command.ExecuteReaderAsync(cancellation);
        var result = new List<CatalogCategoryUsage>();
        while (await reader.ReadAsync(cancellation))
            result.Add(new(reader.GetInt32(0), reader.IsDBNull(1) ? null : reader.GetString(1),
                reader.IsDBNull(2) ? null : JsonSerializer.Deserialize<string[]>(reader.GetString(2)),
                reader.IsDBNull(3) ? null : JsonSerializer.Deserialize<string[]>(reader.GetString(3)), reader.GetBoolean(4)));
        return result;
    }

    private NpgsqlCommand ScopedCommand(NpgsqlConnection db, NpgsqlTransaction tx, string sql)
    {
        var command = new NpgsqlCommand(sql, db, tx);
        command.Parameters.AddWithValue("company", settings.OrganizationId);
        return command;
    }

    private static string LegacyId(string name)
    {
        using var sha = SHA256.Create();
        var bytes = sha.ComputeHash(Encoding.UTF8.GetBytes(name));
        return "legacy-" + string.Concat(bytes.Take(12).Select(value => value.ToString("x2", CultureInfo.InvariantCulture)));
    }
}
