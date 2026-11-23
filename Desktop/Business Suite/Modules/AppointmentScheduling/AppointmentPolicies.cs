using System.Data;
using System.Globalization;
using System.Text.Json;
using System.Text.Json.Nodes;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record ServiceBookingPolicyDraft(int Service,int? Revision,int DefaultMinutes,int Minimum,int Maximum,
    bool Active,bool Required,bool AllowOverride,string[] Categories,string[] Assets);
internal sealed record ServiceBookingPolicyPage(DataTable Rows,bool CanSave);

internal sealed partial class AppointmentRepository
{
    internal async Task<ServiceBookingPolicyPage> ReadBookingPoliciesAsync(CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor=await AuthorizeAsync(db,tx,"view",cancellation);
        bool canSave=actor.CanWriteBranch && await CanWriteAsync(db,tx,actor,"create");
        using var query=Query(db,tx,@"SELECT s.id AS service,s.item_name AS title,p.id,p.revision,
            p.default_duration_minutes,p.min_duration_minutes,p.max_duration_minutes,p.active,p.booking_required,p.allow_duration_override,
            coalesce(p.employee_categories::text,'[]') AS categories,
            coalesce((s.metadata_json::jsonb->'service_resource_requirements'->(p.id::text))::text,'[]') AS assets
            FROM ("+Services+@") s(id,item_name,sales_rate,gst_rate,currency,metadata_json)
            LEFT JOIN public.srm_service_booking_policies p ON p.service_product_id=s.id
                AND p.organization_id=@org AND p.branch_id=@branch AND p.pack_context_id IS NULL
                AND NOT EXISTS (SELECT 1 FROM public.business_pack_record_ownership o WHERE
                    o.resource_table='srm_service_booking_policies' AND o.resource_key=p.id::text)
            ORDER BY s.item_name,s.id");
        var table=new DataTable();
        using var row=await query.ExecuteReaderAsync(cancellation);
        for (int i=0;i<row.FieldCount;i++) table.Columns.Add(row.GetName(i),row.GetFieldType(i));
        while (await row.ReadAsync(cancellation))
        {
            var values=new object[row.FieldCount];
            row.GetValues(values);
            table.Rows.Add(values);
        }
        return new(table,canSave);
    }

    internal async Task<(int Id,int Revision)> SaveBookingPolicyAsync(ServiceBookingPolicyDraft draft,CancellationToken cancellation)
    {
        if (draft.Service<=0 || draft.Revision is <=0 || draft.Minimum<5 || draft.Maximum>720 ||
            draft.DefaultMinutes<draft.Minimum || draft.DefaultMinutes>draft.Maximum ||
            draft.Categories.Length>20 || draft.Assets.Length>4 || draft.Assets.Distinct().Count()!=draft.Assets.Length ||
            draft.Assets.Any(item=>!AssetKinds.Contains(item)))
            throw new InvalidOperationException("Choose permitted default, minimum and maximum durations, categories and resource types.");
        var categories=draft.Categories.Select(value=>string.Join(" ",value.Split((char[]?)null,StringSplitOptions.RemoveEmptyEntries)))
            .Distinct(StringComparer.OrdinalIgnoreCase).ToArray();
        if (categories.Any(item=>item.Length is <1 or >80))
            throw new InvalidOperationException("Employee categories must contain 1 to 80 characters.");
        var assets=draft.Assets.OrderBy(item=>item,StringComparer.Ordinal).ToArray();

        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await AuthorizeAsync(db,tx,"create",cancellation);
        JsonObject metadata;
        using (var product=Query(db,tx,Services+" AND s.id=@service FOR UPDATE OF s",("service",NpgsqlDbType.Integer,draft.Service)))
        using (var row=await product.ExecuteReaderAsync(cancellation))
        {
            if (!await row.ReadAsync(cancellation))
                throw new InvalidOperationException("Choose an active service available in this branch.");
            metadata=JsonNode.Parse(row.GetString(5))!.AsObject();
        }
        int? existingId=null;
        int? revision=null;
        bool same=false;
        using (var prior=Query(db,tx,@"SELECT p.id,p.revision,
            p.default_duration_minutes=@default AND p.min_duration_minutes=@minimum AND p.max_duration_minutes=@maximum
            AND p.active=@active AND p.booking_required=@required AND p.allow_duration_override=@overrides
            AND coalesce(p.employee_categories::jsonb,'[]'::jsonb)=@categories::jsonb,
            EXISTS (SELECT 1 FROM public.business_pack_record_ownership o WHERE
                o.resource_table='srm_service_booking_policies' AND o.resource_key=p.id::text)
            FROM public.srm_service_booking_policies p WHERE p.organization_id=@org AND p.branch_id=@branch
                AND p.pack_context_id IS NULL AND p.service_product_id=@service FOR UPDATE OF p",PolicyArguments(draft,categories)))
        using (var row=await prior.ExecuteReaderAsync(cancellation))
        {
            if (await row.ReadAsync(cancellation))
            {
                if (row.GetBoolean(3))
                    throw new UnauthorizedAccessException("This service booking policy belongs to an operational pack.");
                existingId=row.GetInt32(0);
                revision=row.GetInt32(1);
                same=!row.IsDBNull(2) && row.GetBoolean(2);
            }
        }
        if (revision!=draft.Revision)
            throw new InvalidOperationException("The service policy revision changed. Refresh before saving.");

        var requirements=metadata["service_resource_requirements"] as JsonObject;
        if (requirements is null && metadata["service_resource_requirements"] is not null)
            throw new InvalidOperationException("Review the service's stored resource requirements before saving.");
        var previous=existingId is int current ? requirements?[current.ToString(CultureInfo.InvariantCulture)]?.Deserialize<string[]>() ?? [] : [];
        bool assetsChanged=!previous.OrderBy(item=>item,StringComparer.Ordinal).SequenceEqual(assets);
        if (same && !assetsChanged && existingId is int unchanged && revision is int savedRevision)
            return (unchanged,savedRevision);

        string sql=existingId.HasValue ? @"UPDATE public.srm_service_booking_policies SET default_duration_minutes=@default,
            min_duration_minutes=@minimum,max_duration_minutes=@maximum,active=@active,booking_required=@required,
            allow_duration_override=@overrides,employee_categories=@categories,revision=revision+1,updated_at=now()
            WHERE id=@id AND organization_id=@org AND branch_id=@branch AND revision=@revision RETURNING id,revision"
            : @"INSERT INTO public.srm_service_booking_policies(organization_id,branch_id,service_product_id,default_duration_minutes,
                min_duration_minutes,max_duration_minutes,active,booking_required,allow_duration_override,employee_categories,revision)
            VALUES(@org,@branch,@service,@default,@minimum,@maximum,@active,@required,@overrides,@categories,1) RETURNING id,revision";
        int id,newRevision;
        using (var write=Query(db,tx,sql,PolicyArguments(draft,categories).Concat(new (string,NpgsqlDbType,object?)[]
            {("id",NpgsqlDbType.Integer,existingId),("revision",NpgsqlDbType.Integer,revision)}).ToArray()))
        using (var row=await write.ExecuteReaderAsync(cancellation))
        {
            if (!await row.ReadAsync(cancellation))
                throw new InvalidOperationException("The service policy revision changed. Refresh before saving.");
            id=row.GetInt32(0);
            newRevision=row.GetInt32(1);
        }

        if (assetsChanged)
        {
            if (requirements is null)
            {
                requirements=new JsonObject();
                metadata["service_resource_requirements"]=requirements;
            }
            requirements[id.ToString(CultureInfo.InvariantCulture)]=JsonSerializer.SerializeToNode(assets);
            using var product=Query(db,tx,@"UPDATE public.srm_products SET metadata_json=@metadata,updated_at=now()
                WHERE id=@service AND organization_id=@org",("metadata",NpgsqlDbType.Json,metadata.ToJsonString()),
                ("service",NpgsqlDbType.Integer,draft.Service));
            await product.ExecuteNonQueryAsync(cancellation);
        }
        var snapshot=JsonSerializer.SerializeToNode(draft with {Revision=newRevision,Categories=categories,Assets=assets})!.AsObject();
        await AuditAsync(db,tx,actor.Id,id,existingId.HasValue?"updated":"created",draft.Active?"active":"inactive",newRevision,
            snapshot,cancellation,kind:"service_booking_policy");
        await tx.CommitAsync(cancellation);
        return (id,newRevision);
    }

    private static (string,NpgsqlDbType,object?)[] PolicyArguments(ServiceBookingPolicyDraft draft,string[] categories) =>
        [("service",NpgsqlDbType.Integer,draft.Service),("default",NpgsqlDbType.Integer,draft.DefaultMinutes),
         ("minimum",NpgsqlDbType.Integer,draft.Minimum),("maximum",NpgsqlDbType.Integer,draft.Maximum),
         ("active",NpgsqlDbType.Boolean,draft.Active),("required",NpgsqlDbType.Boolean,draft.Required),
         ("overrides",NpgsqlDbType.Boolean,draft.AllowOverride),("categories",NpgsqlDbType.Json,JsonSerializer.Serialize(categories))];
}
