using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record DealStakeholder(int ContactId,string Role,string Influence,string Notes,bool Primary,string Revision="");
internal sealed record DealStakeholderSnapshot(int Id,string Revision,int Version,List<DealStakeholder> Links,List<DealCaptureChoice> Contacts);

internal sealed partial class CrmDealRepository
{
    internal async Task<DealStakeholderSnapshot> StakeholdersAsync(int id,CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor=await RequireEditorAsync(db,tx,cancellation);
        await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"contacts","view");
        var deal=await LockableDealAsync(db,tx,id,false,cancellation,requireOpen:false);
        List<DealStakeholder> links=await StakeholderLinksAsync(db,tx,deal,false,cancellation);
        using var query=Query(db,tx,@"SELECT p.id,p.full_name,p.company_id FROM public.crm_contacts p
            WHERE p.organization_id=@org AND p.deleted_at IS NULL
            AND (@company IS NULL OR p.company_id IS NULL OR p.company_id=@company) AND "+
            CrmDirectoryWrites.BranchScope("crm_contacts","p",includeShares:true)+" ORDER BY p.full_name,p.id",
            ("company",NpgsqlDbType.Integer,deal["company_id"]));
        var contacts=new List<DealCaptureChoice>();
        using var reader=await query.ExecuteReaderAsync(cancellation);
        while (await reader.ReadAsync(cancellation))
            contacts.Add(new(reader.GetInt32(0),reader.GetString(1),reader.IsDBNull(2)?null:reader.GetInt32(2)));
        if (links.Any(link=>!contacts.Any(contact=>contact.Id==link.ContactId)))
            throw new InvalidOperationException("An existing stakeholder is unavailable in this branch or belongs to another company.");
        return new(id,(string)deal["revision"],(int)deal["version"],links,contacts);
    }

    internal async Task SaveStakeholdersAsync(DealStakeholderSnapshot original,IReadOnlyList<DealStakeholder> draft,
        CancellationToken cancellation)
    {
        if (draft.Count>25 || draft.Select(link=>link.ContactId).Distinct().Count()!=draft.Count ||
            draft.Count(link=>link.Primary)>1 || draft.Any(link=>link.ContactId<=0 || link.Role.Length>80 ||
                link.Influence.Length>40 || link.Notes.Length>10000))
            throw new ArgumentException("Use up to 25 distinct contacts, one primary stakeholder, and values within the field limits.");
        bool hasPrimary=draft.Any(link=>link.Primary);
        var next=draft.Select((link,index)=>link with
        {
            Role=string.IsNullOrWhiteSpace(link.Role)?"Stakeholder":link.Role.Trim(),
            Influence=link.Influence.Trim(),Primary=link.Primary || (!hasPrimary && index==0),Revision=""
        }).ToList();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await RequireEditorAsync(db,tx,cancellation);
        await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"contacts","view");
        var deal=await LockableDealAsync(db,tx,original.Id,true,cancellation,requireOpen:false);
        if ((int)deal["version"]!=original.Version || (string)deal["revision"]!=original.Revision)
            throw new InvalidOperationException("This deal was edited. Refresh its stakeholders and try again.");
        var existing=await StakeholderLinksAsync(db,tx,deal,true,cancellation);
        if (!existing.SequenceEqual(original.Links))
            throw new InvalidOperationException("The stakeholders were edited. Refresh and try again.");
        using(var contacts=Query(db,tx,@"SELECT p.id FROM public.crm_contacts p
            WHERE p.organization_id=@org AND p.deleted_at IS NULL AND p.id=ANY(@ids)
              AND (@company IS NULL OR p.company_id IS NULL OR p.company_id=@company) AND "+
            CrmDirectoryWrites.BranchScope("crm_contacts","p",includeShares:true)+" ORDER BY p.id FOR SHARE OF p",
            ("company",NpgsqlDbType.Integer,deal["company_id"]),("ids",NpgsqlDbType.Array|NpgsqlDbType.Integer,
                existing.Concat(next).Select(link=>link.ContactId).Distinct().ToArray())))
        {
            var visible=await ReadAsync(contacts,cancellation);
            if (visible.Rows.Count!=existing.Concat(next).Select(link=>link.ContactId).Distinct().Count())
                throw new InvalidOperationException("A stakeholder contact is unavailable in this branch or belongs to another company.");
        }
        if (existing.Select(link=>link with {Revision=""}).OrderBy(link=>link.ContactId)
            .SequenceEqual(next.OrderBy(link=>link.ContactId)))
            return;
        int? branch=deal["owning_branch"] as int?;
        if (!branch.HasValue)
            throw new InvalidOperationException("A writable owning branch is required to update deal stakeholders.");
        using(var delete=Query(db,tx,@"WITH removed AS (
            DELETE FROM public.crm_deal_contacts WHERE organization_id=@org AND deal_id=@deal AND NOT contact_id=ANY(@ids) RETURNING id
        ) DELETE FROM public.suite_branch_ownership o USING removed r WHERE o.company_id=@org AND
            o.resource_table='crm_deal_contacts' AND o.resource_key=r.id::text",
            ("deal",NpgsqlDbType.Integer,original.Id),("ids",NpgsqlDbType.Array|NpgsqlDbType.Integer,next.Select(link=>link.ContactId).ToArray())))
            await delete.ExecuteNonQueryAsync(cancellation);
        foreach (var link in next)
        {
            using var upsert=Query(db,tx,@"WITH saved AS (
                INSERT INTO public.crm_deal_contacts (organization_id,deal_id,contact_id,role,influence_level,notes,is_primary,
                    created_by_user_id,updated_by_user_id)
                VALUES (@org,@deal,@contact,@role,NULLIF(@influence,''),NULLIF(@notes,''),@primary,@actor,@actor)
                ON CONFLICT (deal_id,contact_id) DO UPDATE SET role=excluded.role,influence_level=excluded.influence_level,
                    notes=excluded.notes,is_primary=excluded.is_primary,updated_by_user_id=excluded.updated_by_user_id,updated_at=now()
                WHERE crm_deal_contacts.organization_id=@org RETURNING id
            ) INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
            SELECT 'crm_deal_contacts',id::text,@org,@owner_branch,'desktop-crm' FROM saved
            ON CONFLICT DO NOTHING",
                ("deal",NpgsqlDbType.Integer,original.Id),("contact",NpgsqlDbType.Integer,link.ContactId),
                ("role",NpgsqlDbType.Text,link.Role),("influence",NpgsqlDbType.Text,link.Influence),("notes",NpgsqlDbType.Text,link.Notes),
                ("primary",NpgsqlDbType.Boolean,link.Primary),("actor",NpgsqlDbType.Integer,actor.Id),("owner_branch",NpgsqlDbType.Integer,branch));
            await upsert.ExecuteNonQueryAsync(cancellation);
        }
        int? primary=next.FirstOrDefault(link=>link.Primary)?.ContactId;
        using(var update=Query(db,tx,@"UPDATE public.crm_deals SET contact_id=@primary,version=version+1,
            updated_by_user_id=@actor,updated_at=now() WHERE organization_id=@org AND id=@deal",
            ("primary",NpgsqlDbType.Integer,primary),("actor",NpgsqlDbType.Integer,actor.Id),("deal",NpgsqlDbType.Integer,original.Id)))
            await update.ExecuteNonQueryAsync(cancellation);
        await WriteAuditAsync(db,tx,actor.Id,original.Id,false,[
            ("stakeholders",existing.Select(link=>link with {Revision=""}),next),("contact_id",deal["contact_id"] as int?,primary)
        ],cancellation);
        tx.Commit();
    }

    private async Task<List<DealStakeholder>> StakeholderLinksAsync(NpgsqlConnection db,NpgsqlTransaction tx,DataRow deal,
        bool locked,CancellationToken cancellation)
    {
        var links=new List<DealStakeholder>();
        using var query=Query(db,tx,@"SELECT l.organization_id,l.contact_id,COALESCE(l.role,'Stakeholder'),COALESCE(l.influence_level,''),
                COALESCE(l.notes,''),COALESCE(l.is_primary,false),l.xmin::text,o.branch_id
            FROM public.crm_deal_contacts l
            LEFT JOIN public.suite_branch_ownership o ON o.company_id=@org AND o.resource_table='crm_deal_contacts'
                AND o.resource_key=l.id::text
            WHERE l.deal_id=@deal ORDER BY l.is_primary DESC NULLS LAST,l.id"+
            (locked?" FOR UPDATE OF l":""),
            ("deal",NpgsqlDbType.Integer,deal["id"]));
        using var reader=await query.ExecuteReaderAsync(cancellation);
        while (await reader.ReadAsync(cancellation))
        {
            if (reader.IsDBNull(0) || reader.GetInt32(0)!=settings.OrganizationId)
                throw new InvalidOperationException("A stakeholder lacks verified company ownership.");
            if (!reader.IsDBNull(7) && reader.GetInt32(7)!=(deal["owning_branch"] as int?))
                throw new InvalidOperationException("A stakeholder is owned by a different branch.");
            links.Add(new(reader.GetInt32(1),reader.GetString(2),reader.GetString(3),reader.GetString(4),reader.GetBoolean(5),reader.GetString(6)));
        }
        if (links.Count==0 && deal["contact_id"] is int contact)
            links.Add(new(contact,"Primary","","",true,"legacy"));
        return links;
    }
}
