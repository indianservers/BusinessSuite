using System.Data;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal static partial class LeadStore
{
    private static async Task RecordLeadAttendanceAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopDatabaseSettings settings,
        LeadKey key,DataRow lead,int meeting,int actor,bool demo,CancellationToken cancellation)
    {
        int org=settings.OrganizationId;
        DateTime now=DateTime.UtcNow;
        var details=ReadDetails(lead);
        details["lastResponseAt"]=now;
        await WriteState(db,tx,org,key.Id,details,key.StateRevision,cancellation);
        if (!demo) return;

        using var config=Cmd(db,tx,@"SELECT settings_json->'salesProcess'->>'pipelineId'
            FROM public.crm_lead_management_config
            WHERE organization_id=@org AND settings_json->'salesProcess'->>'enabled'='true' FOR SHARE",
            ("org",NpgsqlDbType.Integer,org));
        var salesPipeline=await config.ExecuteScalarAsync(cancellation);
        if (salesPipeline is null) return;
        int? deal=lead["converted_deal_id"] as int?;
        string metadata=JsonSerializer.Serialize(new {salesAutomation="demo_completed",meetingId=meeting,dealId=deal});
        await AddLeadPendingTaskAsync(db,tx,settings,key.Id,lead,actor,"Follow up after completed demo",metadata,
            now.AddDays(1),cancellation);
        if (deal.HasValue)
        {
            if (salesPipeline is not string pipeline || !int.TryParse(pipeline,out int pipelineId) || pipelineId<=0)
                throw new InvalidOperationException("The enabled sales process has no valid pipeline.");
            await new CrmDealRepository(settings).AdvanceAfterDemoAsync(db,tx,deal.Value,pipelineId,cancellation);
        }
    }

    internal static async Task<int> AddLeadPendingTaskAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopDatabaseSettings settings,
        int leadId,DataRow lead,int actor,string title,string metadata,DateTime due,CancellationToken cancellation,
        string kind="task",int? ownerOverride=null)
    {
        int org=settings.OrganizationId;
        int? branch=settings.BranchId ?? lead["branch_id"] as int?;
        int owner=ownerOverride ?? lead["owner_user_id"] as int? ?? actor;
        using var task=Cmd(db,tx,@"INSERT INTO public.crm_activities (organization_id,branch_id,owner_user_id,
            entity_type,entity_id,lead_id,activity_type,subject,title,status,due_date,activity_date,metadata_json,
            created_by_user_id,updated_by_user_id)
            VALUES (@org,@branch,@owner,'lead',@lead,@lead,@kind,@title,@title,'Pending',@due,@due,@metadata,@actor,@actor) RETURNING id",
            ("org",NpgsqlDbType.Integer,org),("branch",NpgsqlDbType.Integer,branch),("owner",NpgsqlDbType.Integer,owner),
            ("lead",NpgsqlDbType.Integer,leadId),("due",NpgsqlDbType.TimestampTz,due),("metadata",NpgsqlDbType.Json,metadata),
            ("actor",NpgsqlDbType.Integer,actor),("title",NpgsqlDbType.Text,title),("kind",NpgsqlDbType.Text,kind));
        int id=(int)(await task.ExecuteScalarAsync(cancellation))!;
        if (branch.HasValue)
            await AddOwnership(db,tx,org,"crm_activities",id,branch.Value,cancellation);
        await CrmDirectoryWrites.Audit(db,tx,"crm_activities",org,id,actor,"CREATE",cancellation,"Lead follow-up task");
        return id;
    }
}
