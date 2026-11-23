using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class CrmDealRepository
{
    internal async Task ChangeArchiveAsync(int id,string revision,bool archive,CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        if (!actor.IsSuperuser || settings.BranchId is null)
            throw new UnauthorizedAccessException("Desktop Deal archive actions require a Suite superuser in a writable branch.");
        await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"deals","delete");

        using var verify=Query(db,tx,@"SELECT d.xmin::text,(d.deleted_at IS NOT NULL),d.company_id,d.contact_id,pipeline_id,stage_id
            FROM public.crm_deals d WHERE d.organization_id=@org AND d.id=@id AND "+
            CrmDirectoryWrites.BranchScope("crm_deals","d")+" FOR UPDATE OF d",("id",NpgsqlDbType.Integer,id));
        int? company;
        int? contact;
        int pipeline;
        int stage;
        using(var reader=await verify.ExecuteReaderAsync(cancellation))
        {
            if (!await reader.ReadAsync(cancellation) || reader.GetString(0)!=revision || reader.GetBoolean(1)==archive)
                throw new InvalidOperationException("This deal was changed or is outside the current branch. Refresh the list.");
            company=reader.IsDBNull(2)?null:reader.GetInt32(2);
            contact=reader.IsDBNull(3)?null:reader.GetInt32(3);
            pipeline=reader.GetInt32(4);
            stage=reader.GetInt32(5);
        }
        if (!archive)
        {
            using (var merged=Query(db,tx,@"SELECT 1 FROM public.crm_activities WHERE organization_id=@org AND entity_type='deal'
                AND entity_id=@id AND activity_type='duplicate_merge' AND metadata_json->>'loserId'=@id::text LIMIT 1",
                ("id",NpgsqlDbType.Integer,id)))
                if (await merged.ExecuteScalarAsync(cancellation) is not null)
                    throw new InvalidOperationException("This deal was merged. Use the surviving deal.");
            if (company.HasValue)
            {
                await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"accounts","view");
                using var linked=Query(db,tx,@"SELECT c.id FROM public.crm_companies c WHERE c.organization_id=@org AND
                    c.id=@id AND c.deleted_at IS NULL AND "+CrmDirectoryWrites.BranchScope("crm_companies","c",includeShares:true)+
                    " FOR SHARE OF c",("id",NpgsqlDbType.Integer,company));
                if (await linked.ExecuteScalarAsync(cancellation) is null)
                    throw new InvalidOperationException("Restore or regain access to the linked company first.");
            }
            if (contact.HasValue)
            {
                await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"contacts","view");
                using var linked=Query(db,tx,@"SELECT c.id FROM public.crm_contacts c WHERE c.organization_id=@org
                    AND c.id=@id AND c.deleted_at IS NULL AND "+CrmDirectoryWrites.BranchScope("crm_contacts","c",includeShares:true)+
                    " FOR SHARE OF c",("id",NpgsqlDbType.Integer,contact));
                if (await linked.ExecuteScalarAsync(cancellation) is null)
                    throw new InvalidOperationException("Restore or regain access to the linked contact first.");
            }
            using var source=Query(db,tx,@"SELECT p.id FROM public.crm_pipelines p JOIN public.crm_pipeline_stages s
                ON s.pipeline_id=p.id AND s.id=@stage AND s.deleted_at IS NULL
                   AND (s.organization_id=@org OR s.organization_id IS NULL)
                WHERE p.organization_id=@org AND p.id=@pipeline AND p.deleted_at IS NULL FOR SHARE OF p,s",
                ("pipeline",NpgsqlDbType.Integer,pipeline),("stage",NpgsqlDbType.Integer,stage));
            if (await source.ExecuteScalarAsync(cancellation) is null)
                throw new InvalidOperationException("Restore the linked pipeline and stage first.");
        }
        using var update=Query(db,tx,@"WITH original AS (
            SELECT to_jsonb(d) AS old FROM public.crm_deals d WHERE d.organization_id=@org AND d.id=@id
        ), changed AS (
            UPDATE public.crm_deals d SET deleted_at=CASE WHEN @archive THEN now() ELSE NULL END,
                updated_at=now(),updated_by_user_id=@actor,version=CASE WHEN @archive THEN version ELSE version+1 END
            WHERE d.organization_id=@org AND d.id=@id RETURNING to_jsonb(d) AS new
        ) INSERT INTO public.audit_logs (organization_id,user_id,actor_authenticated,method,entity_type,entity_id,action,
            description,module,old_values,new_values)
          SELECT @org,@actor,true,'CRM','deals',@id,@action,@description,'crm',original.old::text,changed.new::text
          FROM original CROSS JOIN changed",("id",NpgsqlDbType.Integer,id),("archive",NpgsqlDbType.Boolean,archive),
            ("actor",NpgsqlDbType.Integer,actor.Id),("action",NpgsqlDbType.Text,archive?"DELETE":"RESTORE"),
            ("description",NpgsqlDbType.Text,archive?"CRM deal archived":"CRM record restored from recycle bin"));
        await update.ExecuteNonQueryAsync(cancellation);
        tx.Commit();
    }

    private async Task<bool> CanArchiveAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor)
    {
        if (!actor.IsSuperuser || !actor.CanWriteBranch || settings.BranchId is null)
            return false;
        try
        {
            await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"deals","delete");
            return true;
        }
        catch(UnauthorizedAccessException) {return false;}
    }
}
