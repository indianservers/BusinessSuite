using System.Data;
using Npgsql;

namespace Business_Suite;

internal sealed partial class SharedCatalogRepository
{
    internal async Task SetArchivedAsync(int id, string revision, bool archive, CancellationToken cancellation)
    {
        if (settings.BranchId is not int branch)
            throw new InvalidOperationException("Choose a branch before changing the catalog.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.ReadCommitted);
        var actor = await settings.VerifyWriteTargetAsync(db, tx, cancellation);
        await RequireCatalogEditAsync(db, tx, branch, actor);

        string name;
        using (var item = new NpgsqlCommand(@"
            SELECT p.item_name,p.active,p.xmin::text||':'||COALESCE(details.xmin::text,'-')" +
            ProductAndDetail + ProductVisibility + @"
            AND p.id=@id AND details.workspace_id IS NULL FOR UPDATE OF p", db, tx))
        {
            BindProductScope(item, settings.OrganizationId, branch, actor);
            item.Parameters.AddWithValue("id", id);
            using var reader = await item.ExecuteReaderAsync(cancellation);
            if (!await reader.ReadAsync(cancellation))
                throw new InvalidOperationException("This offering is unavailable or requires its workspace catalog.");
            if (reader.GetString(2) != revision || reader.GetBoolean(1) != archive)
                throw new InvalidOperationException("The offering changed. Search again and review its status.");
            name = reader.GetString(0);
        }

        await RequireAffectedBranchesAsync(db, tx, id, branch, cancellation);

        using var save = new NpgsqlCommand(@"
            WITH changed AS (
                UPDATE public.srm_products SET active=@active WHERE id=@id
                RETURNING id,product_type,unit_code,metadata_json
            ), detail AS (
                INSERT INTO public.shared_catalog_details
                    (organization_id,product_id,service_id,unit,images,custom_fields,pricing_options,version)
                SELECT @company,CASE WHEN product_type IS DISTINCT FROM 'service' THEN id END,
                    CASE WHEN product_type='service' THEN id END,COALESCE(NULLIF(unit_code,''),'unit'),
                    COALESCE(metadata_json->'images','[]'::json),'{}','[]',1 FROM changed
                WHERE NOT EXISTS (SELECT 1 FROM public.shared_catalog_details existing
                    WHERE existing.product_id=CASE WHEN product_type IS DISTINCT FROM 'service' THEN changed.id END
                        OR existing.service_id=CASE WHEN product_type='service' THEN changed.id END)
            ), versioned AS (
                UPDATE public.shared_catalog_details d SET version=d.version+1 FROM changed
                WHERE d.organization_id=@company
                    AND CASE WHEN changed.product_type='service' THEN d.service_id=changed.id ELSE d.product_id=changed.id END
            )
            INSERT INTO public.audit_logs (organization_id,user_id,actor_authenticated,method,endpoint,
                entity_type,entity_id,action,description,module,old_values,new_values)
            VALUES (@company,@actor,true,'CRM','/crm/catalog/'||@id,'crm_catalog',@id,'UPDATE',
                @description,'crm',json_build_object('active',NOT @active)::text,
                json_build_object('active',@active,'branch_id',@branch)::text)", db, tx);
        save.Parameters.AddWithValue("id", id);
        save.Parameters.AddWithValue("company", settings.OrganizationId);
        save.Parameters.AddWithValue("branch", branch);
        save.Parameters.AddWithValue("actor", actor.Id);
        save.Parameters.AddWithValue("active", !archive);
        save.Parameters.AddWithValue("description", (archive ? "Archived offering " : "Restored offering ") + name);
        await save.ExecuteNonQueryAsync(cancellation);
        tx.Commit();
    }

    private async Task RequireAffectedBranchesAsync(NpgsqlConnection db, NpgsqlTransaction tx, int id,
        int branch, CancellationToken cancellation)
    {
        var affectedBranches = new List<int>();
        using (var available = new NpgsqlCommand(@"
            SELECT b.id FROM public.branches b JOIN public.srm_products p ON p.id=@id
            WHERE b.company_id=@company AND b.is_active
                AND NOT EXISTS (SELECT 1 FROM public.suite_branch_lifecycle l
                    WHERE l.branch_id=b.id AND l.deleted_at IS NOT NULL)
                AND COALESCE((p.metadata_json->'catalog_branches'->'overrides'->>b.id::text)::boolean,
                    (p.metadata_json->'catalog_branches'->>'default')::boolean,true)
            ORDER BY b.id", db, tx))
        {
            available.Parameters.AddWithValue("id", id);
            available.Parameters.AddWithValue("company", settings.OrganizationId);
            using var reader = await available.ExecuteReaderAsync(cancellation);
            while (await reader.ReadAsync(cancellation))
                affectedBranches.Add(reader.GetInt32(0));
        }
        foreach (int destination in affectedBranches.Where(value => value != branch))
        {
            var other = await settings.ForScope(settings.OrganizationId, destination)
                .VerifyWriteTargetAsync(db, tx, cancellation);
            await RequireCatalogEditAsync(db, tx, destination, other);
        }
    }

    private async Task RequireCatalogEditAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, DesktopActor actor,
        string action = "edit")
    {
        var grant = await DesktopModuleAccess.RequireAsync(db, tx, settings.OrganizationId, branch,
            actor, "srm", action, "srm_manage", "srm_admin");
        if (grant.Scope != "organization")
            throw new UnauthorizedAccessException("Changing an offering requires organization catalog access.");
    }
}
