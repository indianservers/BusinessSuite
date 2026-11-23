using System.Data;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record DealCaptureChoice(int? Id,string Name,int? Parent=null);
internal sealed record DealCaptureOptions(List<DealCaptureChoice> Companies,List<DealCaptureChoice> Contacts,
    List<DealCaptureChoice> Stages,string Currency);
internal sealed record DealCaptureDraft(string Name,string Description,int? Company,int? Contact,int Stage,string Currency,
    decimal Amount,DateTime? ExpectedClose,string Source,string DuplicateReason);

internal sealed partial class CrmDealRepository
{
    internal async Task<DealCaptureOptions> CaptureOptionsAsync(CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor=await RequireCaptureAsync(db,tx,cancellation);
        bool companies=await CanViewAsync(db,tx,actor,AccountsPermission,ManageAccounts);
        bool contacts=await CanViewAsync(db,tx,actor,ContactsPermission,ManageContacts);
        var customers=new List<DealCaptureChoice> {new(null,"No linked company")};
        var people=new List<DealCaptureChoice> {new(null,"No linked contact")};
        if (companies)
            await Read(customers,@"SELECT c.id,c.name,NULL::int FROM public.crm_companies c WHERE c.organization_id=@org
                AND c.deleted_at IS NULL AND c.status='Active' AND "+CrmDirectoryWrites.BranchScope("crm_companies","c",includeShares:true)+@"
                AND NOT EXISTS (SELECT 1 FROM public.srm_anonymous_cash_accounts a WHERE a.organization_id=@org AND a.customer_id=c.id)
                ORDER BY c.name,c.id");
        if (contacts)
            await Read(people,@"SELECT c.id,c.full_name,c.company_id FROM public.crm_contacts c WHERE c.organization_id=@org
                AND c.deleted_at IS NULL AND "+CrmDirectoryWrites.BranchScope("crm_contacts","c",includeShares:true)+@"
                ORDER BY c.full_name,c.id");
        var stages=new List<DealCaptureChoice>();
        await Read(stages,@"SELECT s.id,p.name||' · '||s.name,p.id FROM public.crm_pipelines p JOIN public.crm_pipeline_stages s
            ON s.pipeline_id=p.id AND s.organization_id=@org AND "+AvailableCaptureStage+@"
            WHERE p.organization_id=@org AND p.active AND p.deleted_at IS NULL
            ORDER BY p.is_default DESC NULLS LAST,p.name,s.position NULLS LAST,s.id");
        using var currency=Query(db,tx,"SELECT COALESCE(default_currency,'INR') FROM public.companies WHERE id=@org");
        return new(customers,people,stages,(string)(await currency.ExecuteScalarAsync(cancellation))!);

        async Task Read(List<DealCaptureChoice> target,string sql)
        {
            using var query=Query(db,tx,sql);
            using var rows=await query.ExecuteReaderAsync(cancellation);
            while (await rows.ReadAsync(cancellation))
                target.Add(new(rows.GetInt32(0),rows.GetString(1),rows.IsDBNull(2)?null:rows.GetInt32(2)));
        }
    }

    private const string AvailableCaptureStage=@"s.active AND s.deleted_at IS NULL AND NOT COALESCE(s.is_won,false)
        AND NOT COALESCE(s.is_lost,false) AND COALESCE(lower(s.stage_type),'open') NOT IN ('won','lost')";

    internal async Task<int> CaptureAsync(DealCaptureDraft draft,CancellationToken cancellation)
    {
        string name=draft.Name.Trim(),currency=draft.Currency.Trim().ToUpperInvariant(),source=draft.Source.Trim();
        if (name.Length is <1 or >180 || draft.Description.Length>10000 || draft.DuplicateReason.Length>1000 ||
            source.Length>80 || draft.Amount<0 || draft.Amount>9999999999.99m || Math.Round(draft.Amount,2)!=draft.Amount ||
            currency.Length!=3 || currency.Any(value=>value<'A'||value>'Z'))
            throw new ArgumentException("Enter a deal name of up to 180 characters, three-letter currency and a nonnegative value.");
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await RequireCaptureAsync(db,tx,cancellation);
        using(var serialize=Query(db,tx,"SELECT pg_advisory_xact_lock(720000000::bigint+@org)"))
            await serialize.ExecuteNonQueryAsync(cancellation);
        await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        var actor=await RequireCaptureAsync(db,tx,cancellation);
        await GuardCaptureEffectsAsync(db,tx,cancellation);
        await CheckCaptureLinksAsync(db,tx,actor,draft,cancellation);
        using var stageQuery=Query(db,tx,@"SELECT s.id,s.name,s.pipeline_id,s.probability,s.policy_json::text AS policy
            FROM public.crm_pipeline_stages s JOIN public.crm_pipelines p ON p.id=s.pipeline_id
            WHERE p.organization_id=@org AND p.active AND p.deleted_at IS NULL
                AND s.organization_id=@org AND s.id=@stage AND "+AvailableCaptureStage+" FOR UPDATE OF s",
            ("stage",NpgsqlDbType.Integer,draft.Stage));
        var stageRows=await ReadAsync(stageQuery,cancellation);
        if (stageRows.Rows.Count==0)
            throw new InvalidOperationException("Choose an active open stage from the pipeline.");
        DataRow stage=stageRows.Rows[0];
        int pipeline=(int)stage["pipeline_id"];
        int probability=stage["probability"] as int? ?? 0;
        if (probability<0||probability>100)
            throw new InvalidOperationException("The pipeline stage probability must be between 0 and 100.");
        await CheckCapturePolicyAsync(db,tx,draft,stage,cancellation);
        bool duplicate;
        using(var match=Query(db,tx,@"SELECT EXISTS(SELECT 1 FROM public.crm_deals d WHERE d.organization_id=@org
            AND d.deleted_at IS NULL AND (@company IS NULL OR d.company_id=@company)
            AND lower(trim(d.name))=lower(@name) AND "+CrmDirectoryWrites.BranchScope("crm_deals","d")+")",
            ("company",NpgsqlDbType.Integer,draft.Company),("name",NpgsqlDbType.Text,name)))
            duplicate=(bool)(await match.ExecuteScalarAsync(cancellation))!;
        if (duplicate && draft.DuplicateReason.Trim().Length<5)
            throw new InvalidOperationException("A deal with this name already exists for the company. Enter a reason to create a separate deal.");

        using var insert=Query(db,tx,@"INSERT INTO public.crm_deals (organization_id,branch_id,company_id,contact_id,owner_user_id,
            pipeline_id,stage_id,name,description,currency,amount,probability,expected_revenue,expected_close_date,
            status,priority,deal_type,lead_source,source,position,version,created_by_user_id,updated_by_user_id)
            VALUES (@org,@scope_branch,@company,@contact,@actor,@pipeline,@stage,@name,@description,@currency,@amount,
                @probability,@expected,@close,'Open','Medium','New Business',@source,@source,
                (SELECT COALESCE(max(position),0)+1 FROM public.crm_deals WHERE organization_id=@org AND stage_id=@stage AND deleted_at IS NULL),
                1,@actor,@actor)
            RETURNING id",("company",NpgsqlDbType.Integer,draft.Company),("contact",NpgsqlDbType.Integer,draft.Contact),
            ("actor",NpgsqlDbType.Integer,actor.Id),("pipeline",NpgsqlDbType.Integer,pipeline),("stage",NpgsqlDbType.Integer,draft.Stage),
            ("name",NpgsqlDbType.Text,name),("description",NpgsqlDbType.Text,draft.Description),("currency",NpgsqlDbType.Text,currency),
            ("amount",NpgsqlDbType.Numeric,draft.Amount),("probability",NpgsqlDbType.Integer,probability),
            ("expected",NpgsqlDbType.Numeric,Math.Round(draft.Amount*probability/100m,2,MidpointRounding.ToEven)),
            ("close",NpgsqlDbType.Date,draft.ExpectedClose?.Date),("source",NpgsqlDbType.Text,source));
        int id=(int)(await insert.ExecuteScalarAsync(cancellation))!;
        using(var own=Query(db,tx,@"INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
            VALUES ('crm_deals',@id::text,@org,@scope_branch,'desktop-crm')",("id",NpgsqlDbType.Integer,id)))
            await own.ExecuteNonQueryAsync(cancellation);
        if (draft.Contact is int contact)
        {
            using var link=Query(db,tx,@"WITH inserted AS (
                INSERT INTO public.crm_deal_contacts (organization_id,deal_id,contact_id,role,is_primary,created_by_user_id,updated_by_user_id)
                VALUES (@org,@id,@contact,'Stakeholder',true,@actor,@actor) RETURNING id
            ) INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
              SELECT 'crm_deal_contacts',id::text,@org,@scope_branch,'desktop-crm' FROM inserted",
                ("id",NpgsqlDbType.Integer,id),("contact",NpgsqlDbType.Integer,contact),("actor",NpgsqlDbType.Integer,actor.Id));
            await link.ExecuteNonQueryAsync(cancellation);
        }
        await CrmDirectoryWrites.CheckRequiredFieldsAsync(db,tx,"deals",settings.OrganizationId,id,cancellation);
        var newRow=await LockableDealAsync(db,tx,id,false,cancellation);
        await AddHistoryAsync(db,tx,actor.Id,newRow,("stage_id",null,draft.Stage),cancellation,"Deal entered initial pipeline stage");
        await QueueStageEventAsync(db,tx,actor.Id,newRow,null,"Created",stage,cancellation);
        await CrmDirectoryWrites.Audit(db,tx,"deals",settings.OrganizationId,id,actor.Id,"CREATE",cancellation);
        if (duplicate)
            await CrmDirectoryWrites.Audit(db,tx,"deals",settings.OrganizationId,id,actor.Id,"DUPLICATE_CONFIRMED",cancellation,draft.DuplicateReason.Trim());
        tx.Commit();
        return id;
    }

    private async Task CheckCaptureLinksAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor,
        DealCaptureDraft draft,CancellationToken cancellation)
    {
        if (draft.Company is int company)
        {
            await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"accounts","view");
            using var query=Query(db,tx,@"SELECT c.id FROM public.crm_companies c WHERE c.organization_id=@org
                AND c.id=@id AND c.deleted_at IS NULL AND c.status='Active' AND "+
                CrmDirectoryWrites.BranchScope("crm_companies","c",includeShares:true)+@"
                AND NOT EXISTS (SELECT 1 FROM public.srm_anonymous_cash_accounts a WHERE a.organization_id=@org AND a.customer_id=c.id)
                FOR SHARE OF c",("id",NpgsqlDbType.Integer,company));
            if (await query.ExecuteScalarAsync(cancellation) is null)
                throw new InvalidOperationException("Choose an active company visible in this branch.");
        }
        if (draft.Contact is int contact)
        {
            await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"contacts","view");
            using var query=Query(db,tx,@"SELECT c.id FROM public.crm_contacts c WHERE c.organization_id=@org
                AND c.id=@id AND c.deleted_at IS NULL AND (c.company_id IS NULL OR c.company_id=@company) AND "+
                CrmDirectoryWrites.BranchScope("crm_contacts","c",includeShares:true)+
                " FOR SHARE OF c",("id",NpgsqlDbType.Integer,contact),("company",NpgsqlDbType.Integer,draft.Company));
            if (await query.ExecuteScalarAsync(cancellation) is null)
                throw new InvalidOperationException("Choose a visible contact linked to the selected company or a standalone contact.");
        }
    }

    private async Task CheckCapturePolicyAsync(NpgsqlConnection db,NpgsqlTransaction tx,DealCaptureDraft draft,DataRow stage,
        CancellationToken cancellation)
    {
        using var parsed=JsonDocument.Parse(stage["policy"] as string??"{}");
        var policy=parsed.RootElement;
        if (policy.TryGetProperty("wip_limit",out var limit) && limit.ValueKind==JsonValueKind.Number && limit.TryGetInt32(out int capacity))
        {
            using var count=Query(db,tx,@"SELECT count(*) FROM public.crm_deals
                WHERE organization_id=@org AND stage_id=@stage AND deleted_at IS NULL",
                ("stage",NpgsqlDbType.Integer,draft.Stage));
            if ((long)(await count.ExecuteScalarAsync(cancellation))!>=capacity)
                throw new InvalidOperationException("The initial stage is at capacity.");
        }
        if (policy.TryGetProperty("approval_required",out var approval) && approval.ValueKind==JsonValueKind.True)
            throw new InvalidOperationException("The initial stage requires an approved deal request. Choose an earlier open stage.");
        if (policy.TryGetProperty("required",out var requirements) && requirements.ValueKind==JsonValueKind.Array)
        {
            var missing=requirements.EnumerateArray().Select(field=>field.GetString()).Where(field=>field switch
            {
                "company_id"=>draft.Company is null,
                "contact_id"=>draft.Contact is null,
                "amount"=>draft.Amount==0,
                "expected_close_date"=>draft.ExpectedClose is null,
                "lead_source"=>string.IsNullOrWhiteSpace(draft.Source),
                "next_follow_up_at"=>true,
                _=>false
            }).ToArray();
            if (missing.Length>0)
                throw new InvalidOperationException("Complete the stage requirements: "+string.Join(", ",missing)+".");
        }
    }

    private async Task<bool> CanCaptureAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor)
    {
        if (!actor.IsSuperuser || !actor.CanWriteBranch || settings.BranchId is null)
            return false;
        try
        {
            await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"deals","create");
            return true;
        }
        catch(UnauthorizedAccessException) { return false; }
    }

    private async Task<DesktopActor> RequireCaptureAsync(NpgsqlConnection db,NpgsqlTransaction tx,CancellationToken cancellation)
    {
        var actor=await CrmDirectoryWrites.RequireCrmActorAsync(settings,db,tx,cancellation,"deals","create");
        if (!actor.IsSuperuser || !actor.CanWriteBranch || settings.BranchId is null)
            throw new UnauthorizedAccessException("Quick deal capture requires a Suite superuser in a writable branch.");
        return actor;
    }

    private async Task GuardCaptureEffectsAsync(NpgsqlConnection db,NpgsqlTransaction tx,CancellationToken cancellation)
    {
        using var guard=Query(db,tx,@"SELECT
            EXISTS (SELECT 1 FROM public.crm_territories WHERE organization_id=@org AND deleted_at IS NULL AND is_active),
            EXISTS (SELECT 1 FROM public.crm_webhooks WHERE organization_id=@org AND deleted_at IS NULL AND is_active
                AND events::jsonb ? 'deal.created')");
        using var reader=await guard.ExecuteReaderAsync(cancellation);
        await reader.ReadAsync(cancellation);
        if (reader.GetBoolean(0))
            throw new InvalidOperationException("This company has active territory routing. Use the CRM workflow that resolves the territory and owner.");
        if (reader.GetBoolean(1))
            throw new InvalidOperationException("This company has an active deal-created webhook. Its configured delivery requires the CRM service.");
    }
}
