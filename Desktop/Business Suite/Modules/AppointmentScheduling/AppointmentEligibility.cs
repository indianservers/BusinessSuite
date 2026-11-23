using System.Data;
using System.Text.Json;
using System.Text.Json.Nodes;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record AppointmentEligibilityPage(string Service,int PolicyRevision,bool PolicyActive,DataTable Candidates,bool CanSave);
internal sealed record AppointmentEligibilityDraft(int Policy,int PolicyRevision,int Provider,int Employee,int? Revision,bool Active);

internal sealed partial class AppointmentRepository
{
    private const string EligibilityProviderSource = @"
        FROM public.srm_industry_records r JOIN public.employees e ON e.id::text=r.data->>'employee_id'
        JOIN public.branches b ON b.id=e.branch_id AND b.company_id=@org AND b.is_active
        WHERE r.organization_id=@org AND r.branch_id=@branch AND r.kind='resource' AND r.status='active'
         AND r.data->>'resource_type' IN ("+ProviderTypes+@") AND e.branch_id=@branch AND e.deleted_at IS NULL
         AND e.status IN ('Active','Probation','On Leave') AND "+Legacy;

    internal async Task<AppointmentEligibilityPage> ReadAppointmentEligibilityAsync(int policy,CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor=await AuthorizeAsync(db,tx,"view",cancellation);
        var selected=await ReadEligibilityPolicyAsync(db,tx,policy,false,cancellation);
        bool canSave=actor.CanWriteBranch && await CanWriteAsync(db,tx,actor,"create");
        using var query=Query(db,tx,@"WITH provider AS (
                SELECT r.id,r.title,e.id AS employee,concat(e.employee_id,' · ',e.first_name,' ',e.last_name) AS employee_name,
                    coalesce(e.work_categories::text,'[]') AS categories "
                +EligibilityProviderSource+@"
            )
            SELECT r.id,r.title,r.employee,r.employee_name,r.categories,l.revision,coalesce(l.active,false) AS active,
                CASE WHEN l.id IS NULL THEN 'Not eligible' WHEN l.active THEN 'Eligible' ELSE 'Inactive' END AS status
            FROM provider r LEFT JOIN public.srm_service_specialist_eligibility l ON l.provider_resource_id=r.id
                AND l.booking_policy_id=@policy AND l.organization_id=@org AND l.branch_id=@branch AND l.pack_context_id IS NULL
                AND NOT EXISTS (SELECT 1 FROM public.business_pack_record_ownership owner
                    WHERE owner.resource_table='srm_service_specialist_eligibility' AND owner.resource_key=l.id::text)
            ORDER BY r.title,r.id",("policy",NpgsqlDbType.Integer,policy));
        var table=new DataTable();
        using var rows=await query.ExecuteReaderAsync(cancellation);
        for(int i=0;i<rows.FieldCount;i++) table.Columns.Add(rows.GetName(i),rows.GetFieldType(i));
        while(await rows.ReadAsync(cancellation))
        {
            var values=new object[rows.FieldCount];
            rows.GetValues(values);
            table.Rows.Add(values);
        }
        return new(selected.Name,selected.Revision,selected.Active,table,canSave);
    }

    internal async Task<(int Id,int Revision)> SaveAppointmentEligibilityAsync(AppointmentEligibilityDraft draft,CancellationToken cancellation)
    {
        if (draft.Policy<=0 || draft.PolicyRevision<=0 || draft.Provider<=0 || draft.Employee<=0 || draft.Revision is <=0)
            throw new InvalidOperationException("Choose a service policy and active HRMS-linked provider.");
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await AuthorizeAsync(db,tx,"create",cancellation);
        var policy=await ReadEligibilityPolicyAsync(db,tx,draft.Policy,true,cancellation);
        if (draft.PolicyRevision!=policy.Revision)
            throw new InvalidOperationException("The service policy revision changed. Refresh before saving.");
        if (draft.Active && !policy.Active)
            throw new InvalidOperationException("Activate the service policy before adding an eligible specialist.");

        using (var staff=Query(db,tx,"SELECT coalesce(e.work_categories::text,'[]') "+EligibilityProviderSource+
            " AND r.id=@provider AND e.id=@employee FOR SHARE OF r,e",
            ("provider",NpgsqlDbType.Integer,draft.Provider),("employee",NpgsqlDbType.Integer,draft.Employee)))
        {
            if (await staff.ExecuteScalarAsync(cancellation) is not string json)
                throw new InvalidOperationException("Choose an active HRMS-linked provider from this branch.");
            var categories=JsonSerializer.Deserialize<string[]>(json) ?? [];
            if (draft.Active && policy.Categories.Length>0 && !MatchesProviderCategories(categories,policy.Categories))
                throw new InvalidOperationException("This employee does not match the categories allowed by the service policy.");
        }

        int? existingId=null,revision=null;
        bool active=false;
        using (var prior=Query(db,tx,@"SELECT l.id,l.revision,l.active,l.booking_policy_id,
                EXISTS (SELECT 1 FROM public.business_pack_record_ownership owner
                    WHERE owner.resource_table='srm_service_specialist_eligibility' AND owner.resource_key=l.id::text)
            FROM public.srm_service_specialist_eligibility l WHERE l.organization_id=@org AND l.branch_id=@branch
                AND l.pack_context_id IS NULL AND l.service_product_id=@service AND l.provider_resource_id=@provider
            FOR UPDATE OF l",("service",NpgsqlDbType.Integer,policy.Service),("provider",NpgsqlDbType.Integer,draft.Provider)))
        using (var row=await prior.ExecuteReaderAsync(cancellation))
        {
            if(await row.ReadAsync(cancellation))
            {
                if (row.GetBoolean(4) || row.GetInt32(3)!=draft.Policy)
                    throw new InvalidOperationException("The specialist eligibility belongs to a different policy or pack.");
                existingId=row.GetInt32(0);
                revision=row.GetInt32(1);
                active=row.GetBoolean(2);
            }
        }
        if (revision!=draft.Revision || (!existingId.HasValue && !draft.Active))
            throw new InvalidOperationException("The specialist eligibility revision changed. Refresh before saving.");
        if (existingId is int unchanged && active==draft.Active)
            return (unchanged,revision!.Value);

        string sql=existingId.HasValue ? @"UPDATE public.srm_service_specialist_eligibility SET
            active=@active,revision=revision+1,updated_at=now()
            WHERE id=@id AND organization_id=@org AND branch_id=@branch AND revision=@revision RETURNING id,revision"
            : @"INSERT INTO public.srm_service_specialist_eligibility(organization_id,branch_id,booking_policy_id,
                service_product_id,provider_resource_id,active,revision)
            VALUES(@org,@branch,@policy,@service,@provider,true,1) RETURNING id,revision";
        int id,newRevision;
        using (var write=Query(db,tx,sql,("id",NpgsqlDbType.Integer,existingId),("revision",NpgsqlDbType.Integer,revision),
            ("active",NpgsqlDbType.Boolean,draft.Active),("policy",NpgsqlDbType.Integer,draft.Policy),
            ("service",NpgsqlDbType.Integer,policy.Service),("provider",NpgsqlDbType.Integer,draft.Provider)))
        using (var row=await write.ExecuteReaderAsync(cancellation))
        {
            if (!await row.ReadAsync(cancellation))
                throw new InvalidOperationException("The specialist eligibility revision changed. Refresh before saving.");
            id=row.GetInt32(0);
            newRevision=row.GetInt32(1);
        }

        var snapshot=JsonSerializer.SerializeToNode(draft with {Revision=newRevision})!.AsObject();
        await AuditAsync(db,tx,actor.Id,id,existingId.HasValue?"updated":"created",draft.Active?"active":"inactive",newRevision,
            snapshot,cancellation,kind:"service_specialist_eligibility");
        await tx.CommitAsync(cancellation);
        return (id,newRevision);
    }

    private async Task<(int Service,string Name,int Revision,bool Active,string[] Categories)> ReadEligibilityPolicyAsync(
        NpgsqlConnection db,NpgsqlTransaction tx,int policy,bool locked,CancellationToken cancellation)
    {
        using var query=Query(db,tx,@"SELECT s.id,s.item_name,p.revision,p.active,coalesce(p.employee_categories::text,'[]')
            FROM ("+Services+@") s JOIN public.srm_service_booking_policies p ON p.service_product_id=s.id
            WHERE p.id=@policy AND p.organization_id=@org AND p.branch_id=@branch AND p.pack_context_id IS NULL
            AND NOT EXISTS (SELECT 1 FROM public.business_pack_record_ownership owner
                WHERE owner.resource_table='srm_service_booking_policies' AND owner.resource_key=p.id::text)"+
            (locked?" FOR UPDATE OF p":""),("policy",NpgsqlDbType.Integer,policy));
        using var row=await query.ExecuteReaderAsync(cancellation);
        if (!await row.ReadAsync(cancellation))
            throw new InvalidOperationException("The service policy is unavailable in this branch.");
        return (row.GetInt32(0),row.GetString(1),row.GetInt32(2),row.GetBoolean(3),JsonSerializer.Deserialize<string[]>(row.GetString(4)) ?? []);
    }

    private static bool MatchesProviderCategories(IEnumerable<string> actual,IEnumerable<string> required) =>
        actual.Any(value=>required.Any(category=>value.Equals(category,StringComparison.OrdinalIgnoreCase)
            || value.StartsWith(category+" > ",StringComparison.OrdinalIgnoreCase)));
}
