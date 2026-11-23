using System.Data;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;
using Npgsql;

namespace Business_Suite;

internal sealed record CatalogPriceOption(
    [property: JsonPropertyName("id")] string Id,
    [property: JsonPropertyName("name")] string Name,
    [property: JsonPropertyName("amount"), JsonNumberHandling(JsonNumberHandling.AllowReadingFromString | JsonNumberHandling.WriteAsString)] decimal Amount,
    [property: JsonPropertyName("currency")] string Currency,
    [property: JsonPropertyName("interval")] string Interval);

internal sealed record CatalogOfferingDraft(string Kind, string Name, string Code, string Description, string Unit,
    string Currency, string Barcode, string Hsn, decimal Price, decimal Tax, decimal Cost, decimal Mrp,
    decimal Reorder, bool TrackInventory, string[]? CategoryIds = null, CatalogPriceOption[]? AdditionalPrices = null)
{
    internal static CatalogOfferingDraft Empty => new("Product", "", "", "", "unit", "INR", "", "", 0, 0, 0, 0, 0, true);

    internal static CatalogOfferingDraft FromRow(DataRow row) => new((string)row["kind"], (string)row["item_name"],
        (string)row["sku"], (string)row["description"], (string)row["unit"], (string)row["currency"],
        (string)row["barcode"], (string)row["hsn_code"], (decimal)row["price"], (decimal)row["tax"],
        (decimal)row["cost"], (decimal)row["mrp"], (decimal)row["reorder_level"], (bool)row["track_inventory"]);
}

internal sealed partial class SharedCatalogRepository
{
    internal Task<CatalogTaxonomy> OfferingCategoriesAsync(CancellationToken cancellation) =>
        new CatalogCategoriesRepository(settings).LoadAsync(cancellation);

    internal async Task<int> SaveOfferingAsync(int? id, string? revision, CatalogOfferingDraft draft, CancellationToken cancellation)
    {
        if (settings.BranchId is not int branch)
            throw new InvalidOperationException("Choose a branch before saving an offering.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.ReadCommitted);
        var actor = await settings.VerifyWriteTargetAsync(db, tx, cancellation);
        await RequireCatalogEditAsync(db, tx, branch, actor, id.HasValue ? "edit" : "create");
        int saved = await WriteOfferingAsync(db, tx, branch, actor, id, revision, draft, null, cancellation);
        tx.Commit();
        return saved;
    }

    private async Task<int> WriteOfferingAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, DesktopActor actor,
        int? id, string? revision, CatalogOfferingDraft draft, CatalogImportRow? imported, CancellationToken cancellation)
    {
        draft = draft with { Name = draft.Name.Trim(), Code = draft.Code.Trim(), Unit = draft.Unit.Trim(),
            Description = draft.Description.Trim(), Currency = draft.Currency.Trim().ToUpperInvariant(),
            Barcode = draft.Barcode.Trim(), Hsn = draft.Hsn.Trim(), AdditionalPrices = draft.AdditionalPrices?
                .Select(price => price is null ? throw new ArgumentException("A pricing option is missing.") : price with
                {
                    Name = price.Name?.Trim() ?? "",
                    Currency = price.Currency?.Trim().ToUpperInvariant() ?? ""
                }).ToArray() };
        ValidateOffering(draft);
        string[]? categoryIds = null;
        string[]? categoryLabels = null;
        string? category = null;
        if (draft.CategoryIds is { } requested)
        {
            using var guard = new NpgsqlCommand("SELECT id FROM public.companies WHERE id=@company FOR UPDATE", db, tx);
            guard.Parameters.AddWithValue("company", settings.OrganizationId);
            await guard.ExecuteScalarAsync(cancellation);
            var taxonomy = await new CatalogCategoriesRepository(settings).ReadSelectionAsync(db, tx, cancellation);
            var options = taxonomy.Categories
                .SelectMany(parent => new[] { (parent.Id, Label: parent.Name, ParentId: parent.Id, ParentName: parent.Name) }
                    .Concat(parent.Children.Select(child =>
                        (child.Id, Label: $"{parent.Name} > {child.Name}", ParentId: parent.Id, ParentName: parent.Name))))
                .ToDictionary(value => value.Id, StringComparer.Ordinal);
            if (requested.Length > 100 || requested.Any(value => !options.ContainsKey(value)))
                throw new ArgumentException("Select existing categories and subcategories. Reload the choices.");
            categoryIds = requested.Concat(requested.Select(value => options[value].ParentId)).Distinct().ToArray();
            categoryLabels = categoryIds.Select(value => options[value].Label).ToArray();
            category = categoryIds.Length == 0 ? "" : options[categoryIds[0]].ParentName;
        }
        else if (imported is not null)
            category = imported.Category;
        string kind = draft.Kind == "Service" ? "service" : "stock";
        if (id is int existing)
        {
            using var item = new NpgsqlCommand(@"
                SELECT p.xmin::text||':'||COALESCE(details.xmin::text,'-')" + ProductAndDetail + ProductVisibility + @"
                AND p.id=@id AND details.workspace_id IS NULL
                AND (CASE WHEN p.product_type='service' THEN 'service'
                    WHEN p.product_type IN ('membership','subscription','bundle') THEN p.product_type ELSE 'stock' END)=@kind
                FOR UPDATE OF p", db, tx);
            BindProductScope(item, settings.OrganizationId, branch, actor);
            item.Parameters.AddWithValue("id", existing);
            item.Parameters.AddWithValue("kind", kind);
            if (await item.ExecuteScalarAsync(cancellation) is not string current)
                throw new InvalidOperationException("This offering is unavailable or requires a specialized catalog editor.");
            if (current != revision)
                throw new InvalidOperationException("The offering changed. Search again before editing.");
            await RequireAffectedBranchesAsync(db, tx, existing, branch, cancellation);
        }
        const string create = @"INSERT INTO public.srm_products
            (organization_id,sku,item_name,description,product_type,unit_code,barcode,hsn_code,sales_rate,gst_rate,
             purchase_rate,mrp,reorder_level,track_inventory,active,current_quantity,average_cost,min_stock,
             max_stock,batch_tracking,serial_tracking,expiry_tracking,metadata_json,category_name,created_by)
            VALUES (@company,@code,@name,@description,@kind,@unit,NULLIF(@barcode,''),NULLIF(@hsn,''),
             @price,@tax,@cost,@mrp,@reorder,@track,@active,0,0,0,0,false,false,false,
             (jsonb_build_object('currency',@currency,'images',@images::jsonb,'catalog_tags',@tags::jsonb,'catalog_branches',
                jsonb_build_object('default',false,'overrides',jsonb_build_object(@branch::text,true)))
                || @category_meta::jsonb)::json,@category,@actor)
            RETURNING id,product_type,metadata_json";
        const string edit = @"UPDATE public.srm_products SET sku=@code,item_name=@name,description=@description,
            unit_code=@unit,barcode=NULLIF(@barcode,''),hsn_code=NULLIF(@hsn,''),sales_rate=@price,gst_rate=@tax,
            purchase_rate=@cost,mrp=@mrp,reorder_level=@reorder,track_inventory=@track,updated_at=now(),
            category_name=COALESCE(@category,category_name),
            metadata_json=(COALESCE(metadata_json::jsonb,'{}'::jsonb)||jsonb_build_object('currency',@currency)
                || @category_meta::jsonb)::json
            WHERE id=@id RETURNING id,product_type,metadata_json";
        using var save = new NpgsqlCommand("WITH changed AS (" + (id.HasValue ? edit : create) + @"),
            detail AS (
              INSERT INTO public.shared_catalog_details
                (organization_id,product_id,service_id,unit,images,custom_fields,pricing_options,version)
              SELECT @company,CASE WHEN product_type IS DISTINCT FROM 'service' THEN id END,
                CASE WHEN product_type='service' THEN id END,@unit,COALESCE(metadata_json->'images','[]'::json),
                @custom::json,COALESCE(@prices::json,'[]'::json),1
              FROM changed
              WHERE NOT EXISTS (SELECT 1 FROM public.shared_catalog_details d
                WHERE d.product_id=CASE WHEN changed.product_type IS DISTINCT FROM 'service' THEN changed.id END
                   OR d.service_id=CASE WHEN changed.product_type='service' THEN changed.id END)
            ), versioned AS (
              UPDATE public.shared_catalog_details d SET unit=@unit,
                  pricing_options=COALESCE(@prices::json,d.pricing_options),version=d.version+1 FROM changed
              WHERE d.organization_id=@company AND CASE WHEN changed.product_type='service'
                THEN d.service_id=changed.id ELSE d.product_id=changed.id END
            ), audit AS (
              INSERT INTO public.audit_logs (organization_id,user_id,actor_authenticated,method,endpoint,
                entity_type,entity_id,action,description,module,new_values)
              SELECT @company,@actor,true,'CRM','/crm/catalog/'||id,'crm_catalog',id,@action,@audit,'crm',
                json_build_object('branch_id',@branch,'code',@code,'name',@name)::text FROM changed
            ) SELECT id FROM changed", db, tx);
        save.Parameters.AddWithValue("company", settings.OrganizationId);
        save.Parameters.AddWithValue("branch", branch);
        save.Parameters.AddWithValue("actor", actor.Id);
        if (id is int key) save.Parameters.AddWithValue("id", key);
        save.Parameters.AddWithValue("kind", kind);
        save.Parameters.AddWithValue("active", imported?.Active ?? true);
        save.Parameters.AddWithValue("images", JsonSerializer.Serialize(imported?.Images ?? []));
        save.Parameters.AddWithValue("tags", JsonSerializer.Serialize(imported?.Tags ?? []));
        save.Parameters.AddWithValue("custom", imported?.CustomFields ?? "{}");
        save.Parameters.AddWithValue("name", draft.Name);
        save.Parameters.AddWithValue("code", draft.Code);
        save.Parameters.AddWithValue("description", draft.Description);
        save.Parameters.AddWithValue("unit", draft.Unit);
        save.Parameters.AddWithValue("currency", draft.Currency);
        save.Parameters.Add("prices", NpgsqlTypes.NpgsqlDbType.Text).Value =
            draft.AdditionalPrices is null ? DBNull.Value : JsonSerializer.Serialize(draft.AdditionalPrices);
        save.Parameters.Add("category", NpgsqlTypes.NpgsqlDbType.Text).Value = (object?)category ?? DBNull.Value;
        save.Parameters.AddWithValue("category_meta", categoryIds is null ? "{}" :
            JsonSerializer.Serialize(new { catalog_category_ids = categoryIds, catalog_categories = categoryLabels }));
        save.Parameters.AddWithValue("barcode", draft.Barcode);
        save.Parameters.AddWithValue("hsn", draft.Hsn);
        save.Parameters.AddWithValue("price", draft.Price);
        save.Parameters.AddWithValue("tax", draft.Tax);
        save.Parameters.AddWithValue("cost", draft.Cost);
        save.Parameters.AddWithValue("mrp", draft.Mrp);
        save.Parameters.AddWithValue("reorder", draft.Reorder);
        save.Parameters.AddWithValue("track", kind == "stock" && draft.TrackInventory);
        save.Parameters.AddWithValue("action", id.HasValue ? "UPDATE" : "CREATE");
        save.Parameters.AddWithValue("audit", $"Shared {draft.Kind.ToLowerInvariant()} {draft.Name}");
        try
        {
            int saved = (int)(await save.ExecuteScalarAsync(cancellation)
                ?? throw new InvalidOperationException("The offering is unavailable."));
            return saved;
        }
        catch (PostgresException error) when (error.SqlState == PostgresErrorCodes.UniqueViolation &&
            error.ConstraintName is "uq_srm_product_org_sku" or "uq_srm_product_org_barcode")
        {
            throw new InvalidOperationException("That code or barcode is already used by an offering in this company.", error);
        }
    }

    private static void ValidateOffering(CatalogOfferingDraft draft)
    {
        if (draft.Kind is not ("Product" or "Service") || draft.Name.Length is < 1 or > 180 ||
            draft.Code.Length is < 1 or > 80 || draft.Unit.Length is < 1 or > 40 ||
            draft.Barcode.Length > 120 || draft.Hsn.Length > 30 || draft.Description.Length > 50000)
            throw new ArgumentException("Enter a name, code and unit within their field limits.");
        if (!Regex.IsMatch(draft.Currency, "^[A-Z]{3}$"))
            throw new ArgumentException("Enter a three-letter currency code.");
        if (new[] { draft.Price, draft.Cost, draft.Mrp, draft.Tax }.Any(value =>
                value < 0 || value > 9999999999m || decimal.Round(value, 2) != value) ||
            draft.Tax > 100 || draft.Reorder is < 0 or > 9999999999m || decimal.Round(draft.Reorder, 3) != draft.Reorder)
            throw new ArgumentException("Use non-negative amounts, tax up to 100%, and up to three decimals for reorder quantity.");
        if (draft.AdditionalPrices is { } prices)
            ValidateAdditionalPrices(prices);
    }

    internal static void ValidateAdditionalPrices(CatalogPriceOption[] prices)
    {
        if (prices.Length > 30 ||
            prices.Any(price => price is null || string.IsNullOrWhiteSpace(price.Id) || price.Id.Length > 80 ||
                string.IsNullOrWhiteSpace(price.Name) || price.Name.Length > 100 ||
                price.Amount is < 0 or > 9999999999m || decimal.Round(price.Amount, 2) != price.Amount ||
                price.Currency is null || !Regex.IsMatch(price.Currency, "^[A-Z]{3}$") ||
                price.Interval is not ("once" or "day" or "week" or "month" or "year")) ||
            prices.Select(price => price.Id).Distinct(StringComparer.Ordinal).Count() != prices.Length)
            throw new ArgumentException("Enter up to 30 valid pricing options with a name, amount, currency, and billing interval.");
    }
}
