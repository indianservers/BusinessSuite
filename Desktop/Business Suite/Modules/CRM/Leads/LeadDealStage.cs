using System.Data;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal static partial class LeadStore
{
    internal static async Task ApplyDealStageAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopDatabaseSettings settings,
        int deal,int pipeline,string stage,int actor,CancellationToken cancellation,bool convertCustomer=false,int? company=null,int? contact=null)
    {
        int org=settings.OrganizationId;
        using var config=Cmd(db,tx,@"SELECT 1 FROM public.crm_lead_management_config
            WHERE organization_id=@org AND settings_json->'salesProcess'->>'enabled'='true'
                AND settings_json->'salesProcess'->>'pipelineId'=@pipeline::text FOR SHARE",
            ("org",NpgsqlDbType.Integer,org),("pipeline",NpgsqlDbType.Integer,pipeline));
        if (await config.ExecuteScalarAsync(cancellation) is null) return;

        using var linked=Cmd(db,tx,@"SELECT l.id,l.branch_id,l.owner_user_id,("+CrmDirectoryWrites.BranchScope("crm_leads","l")+@") AS in_scope
            FROM public.crm_leads l WHERE l.organization_id=@org AND l.converted_deal_id=@deal AND l.deleted_at IS NULL
            ORDER BY l.id FOR UPDATE OF l",("org",NpgsqlDbType.Integer,org),("deal",NpgsqlDbType.Integer,deal),
            ("scope_branch",NpgsqlDbType.Integer,settings.BranchId));
        var leads=new DataTable();
        using (var reader=await linked.ExecuteReaderAsync(cancellation)) leads.Load(reader);
        if (leads.Rows.Cast<DataRow>().Any(lead=>lead["in_scope"] is not true))
            throw new InvalidOperationException("A linked Lead belongs to another branch. The Deal stage change was cancelled.");

        foreach (DataRow lead in leads.Rows)
        {
            int id=(int)lead["id"];
            DateTime? due=stage=="Proposal Sent"?DateTime.UtcNow.AddDays(2):null;
            if (due.HasValue)
                await AddLeadPendingTaskAsync(db,tx,settings,id,lead,actor,"Follow up on proposal (2 days)",
                    JsonSerializer.Serialize(new {salesAutomation="proposal",dealId=deal}),due.Value,cancellation);
            else if (stage=="Demo Completed")
            {
                using var pending=Cmd(db,tx,@"SELECT EXISTS (SELECT 1 FROM public.crm_activities
                    WHERE organization_id=@org AND lead_id=@lead AND status='Pending' AND metadata_json->>'salesAutomation'='demo_completed')",
                    ("org",NpgsqlDbType.Integer,org),("lead",NpgsqlDbType.Integer,id));
                if (await pending.ExecuteScalarAsync(cancellation) is false)
                    await AddLeadPendingTaskAsync(db,tx,settings,id,lead,actor,"Follow up after completed demo",
                        JsonSerializer.Serialize(new {salesAutomation="demo_completed",dealId=deal}),DateTime.UtcNow.AddDays(1),cancellation);
            }
            string data=due.HasValue?JsonSerializer.Serialize(new {proposalReminder=new {dueAt=due.Value,sent=false}}):"{}";
            using var state=Cmd(db,tx,@"INSERT INTO public.crm_lead_operating_states (organization_id,lead_id,data_json,version)
                VALUES (@org,@lead,@data,2) ON CONFLICT (organization_id,lead_id) DO UPDATE
                SET data_json=((crm_lead_operating_states.data_json::jsonb-'proposalReminder') || excluded.data_json::jsonb)::json,
                    version=crm_lead_operating_states.version+1,updated_at=now()",
                ("org",NpgsqlDbType.Integer,org),("lead",NpgsqlDbType.Integer,id),("data",NpgsqlDbType.Json,data));
            await state.ExecuteNonQueryAsync(cancellation);
        }
        if (convertCustomer && leads.Rows.Count>0)
        {
            if (company.HasValue)
                await ConvertLinkedPartyAsync(db,tx,settings,"crm_companies","account_type='Customer'",company.Value,actor,cancellation);
            if (contact.HasValue)
                await ConvertLinkedPartyAsync(db,tx,settings,"crm_contacts",@"
                    lifecycle_stage='Customer',customer_since=COALESCE(p.customer_since,(now() AT TIME ZONE 'UTC')::date),
                    tags_text=(SELECT string_agg(tag,', ' ORDER BY tag COLLATE ""C"") FROM
                        (SELECT DISTINCT btrim(value) AS tag FROM unnest(string_to_array(COALESCE(p.tags_text,''),',') || ARRAY['Customer']) AS value
                         WHERE btrim(value) NOT IN ('','Opportunity')) AS tags)",contact.Value,actor,cancellation);
        }
    }

    private static async Task ConvertLinkedPartyAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopDatabaseSettings settings,
        string table,string assignments,int id,int actor,CancellationToken cancellation)
    {
        int org=settings.OrganizationId;
        using var convert=Cmd(db,tx,$@"UPDATE public.{table} p SET {assignments},updated_at=now(),updated_by_user_id=@actor
            WHERE p.organization_id=@org AND p.id=@id AND p.deleted_at IS NULL AND "+CrmDirectoryWrites.BranchScope(table,"p"),
            ("org",NpgsqlDbType.Integer,org),("id",NpgsqlDbType.Integer,id),("actor",NpgsqlDbType.Integer,actor),
            ("scope_branch",NpgsqlDbType.Integer,settings.BranchId));
        if (await convert.ExecuteNonQueryAsync(cancellation)!=1)
            throw new InvalidOperationException("A linked customer record is unavailable in this branch. The Deal closure was cancelled.");
        await CrmDirectoryWrites.Audit(db,tx,table,org,id,actor,"UPDATE",cancellation,"Converted to Customer by Deal closure");
    }
}
