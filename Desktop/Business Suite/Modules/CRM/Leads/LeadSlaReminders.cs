using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record LeadSlaReminderResult(int Leads,int Notifications,int Skipped);

internal static partial class LeadStore
{
    internal static async Task<LeadSlaReminderResult> ProcessLeadSlaRemindersAsync(CancellationToken cancellation)
    {
        const int limit=200;
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await RequireLeadSettingsAdminAsync(db,tx,settings,actor);
        int org=settings.OrganizationId;
        using var config=Cmd(db,tx,@"SELECT updated_by FROM public.crm_lead_management_config
            WHERE organization_id=@org FOR SHARE",("org",NpgsqlDbType.Integer,org));
        int? administrator=await config.ExecuteScalarAsync(cancellation) as int?;
        var policy=await ReadPolicy(db,tx,org,cancellation);
        DateTime now=DateTime.UtcNow;
        using var select=Cmd(db,tx,@"SELECT l.*,COALESCE(st.xmin::text,'') AS state_revision,
                COALESCE(st.data_json::text,'{}') AS operating_state,
                COALESCE((SELECT o.branch_id FROM public.suite_branch_ownership o WHERE o.company_id=@org
                    AND o.resource_table='crm_leads' AND o.resource_key=l.id::text),l.branch_id) AS reminder_branch
            FROM public.crm_leads l
            LEFT JOIN public.crm_lead_operating_states st ON st.lead_id=l.id AND st.organization_id=l.organization_id
            WHERE l.organization_id=@org AND l.deleted_at IS NULL AND l.last_contacted_at IS NULL
                AND l.is_converted IS NOT TRUE AND l.status NOT IN ('Lost','Converted') AND l.created_at<@cutoff
                AND st.data_json->>'slaAlertedAt' IS NULL AND COALESCE(st.data_json->>'archived','false')<>'true'
                AND "+CrmDirectoryWrites.BranchScope("crm_leads","l")+@"
            ORDER BY l.created_at,l.id LIMIT @limit FOR UPDATE OF l SKIP LOCKED",
            ("org",NpgsqlDbType.Integer,org),("scope_branch",NpgsqlDbType.Integer,settings.BranchId),
            ("cutoff",NpgsqlDbType.TimestampTz,now.AddHours(-policy.SlaHours)),("limit",NpgsqlDbType.Integer,limit));
        DataTable due;
        using(var rows=await select.ExecuteReaderAsync(cancellation))
            due=await Table(rows,cancellation);
        int escalated=0;
        int notified=0;
        int skipped=0;
        foreach(DataRow row in due.Rows)
        {
            if (row["reminder_branch"] is not int branch)
            {
                skipped++;
                continue;
            }
            int lead=(int)row["id"];
            using(var current=Cmd(db,tx,@"SELECT xmin::text,data_json::text,data_json->>'slaAlertedAt',
                    COALESCE(data_json->>'archived','false')='true'
                FROM public.crm_lead_operating_states WHERE organization_id=@org AND lead_id=@lead FOR UPDATE",
                ("org",NpgsqlDbType.Integer,org),("lead",NpgsqlDbType.Integer,lead)))
            using(var state=await current.ExecuteReaderAsync(cancellation))
                if (await state.ReadAsync(cancellation))
                {
                    if (!state.IsDBNull(2)||state.GetBoolean(3))
                        continue;
                    row["state_revision"]=state.GetString(0);
                    row["operating_state"]=state.GetString(1);
                }
            var recipients=new[] {row["owner_user_id"] as int?,administrator}.OfType<int>().Distinct().OrderBy(id=>id);
            bool any=false;
            foreach(int recipient in recipients)
            {
                if (!await CanNotifyLeadReminderRecipientAsync(db,tx,org,branch,recipient,row,cancellation))
                    continue;
                await NotifyLeadOwnerAsync(db,tx,org,branch,lead,row,actor.Id,"lead_sla","Lead response overdue",
                    $"Contact {Text(row,"full_name")}. The first-response deadline has passed.",cancellation,recipient,"high");
                any=true;
                notified++;
            }
            if (!any)
            {
                skipped++;
                continue;
            }
            var details=ReadDetails(row);
            details["slaAlertedAt"]=now;
            await WriteState(db,tx,org,lead,details,Text(row,"state_revision"),cancellation);
            await AddLeadHistoryAsync(db,tx,org,lead,branch,actor.Id,"sla","First-response deadline escalated",null,"{}",cancellation);
            await CrmDirectoryWrites.Audit(db,tx,"crm_leads",org,lead,actor.Id,"UPDATE",cancellation,
                "First-response deadline escalated");
            escalated++;
        }
        tx.Commit();
        return new(escalated,notified,skipped);
    }
}
