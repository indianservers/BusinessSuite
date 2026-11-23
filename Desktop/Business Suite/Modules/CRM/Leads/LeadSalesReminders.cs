using System.Data;
using System.Globalization;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record LeadSalesReminderResult(bool Enabled,int Manager,int Proposal,int Nurture);

internal static partial class LeadStore
{
    private sealed record SalesReminder(string Key,object Value,int? Recipient,string Title,string Kind);

    internal static async Task<LeadSalesReminderResult> ProcessLeadSalesRemindersAsync(CancellationToken cancellation)
    {
        const int notificationLimit=200;
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await RequireLeadSettingsAdminAsync(db,tx,settings,actor);
        int org=settings.OrganizationId;
        using var config=Cmd(db,tx,@"SELECT settings_json->'salesProcess'
            FROM public.crm_lead_management_config WHERE organization_id=@org FOR SHARE",("org",NpgsqlDbType.Integer,org));
        if (await config.ExecuteScalarAsync(cancellation) is not string json)
            return new(false,0,0,0);
        using var process=JsonDocument.Parse(json);
        if (Nested(process.RootElement,"enabled") is not JsonElement enabled||enabled.ValueKind!=JsonValueKind.True)
            return new(false,0,0,0);
        int? manager=WorkflowInteger(process.RootElement,"managerId");
        DateTime now=DateTime.UtcNow;
        int managerAlerts=0;
        int proposalAlerts=0;
        int nurtureAlerts=0;
        int cursor=0;
        while (managerAlerts+proposalAlerts+nurtureAlerts<notificationLimit)
        {
            using var query=Cmd(db,tx,@"SELECT l.*,st.xmin::text AS state_revision,st.data_json::text AS operating_state,
                    d.status AS reminder_deal_status,
                    COALESCE((SELECT o.branch_id FROM public.suite_branch_ownership o WHERE o.company_id=@org
                        AND o.resource_table='crm_leads' AND o.resource_key=l.id::text),l.branch_id) AS reminder_branch
                FROM public.crm_leads l JOIN public.crm_lead_operating_states st
                    ON st.organization_id=l.organization_id AND st.lead_id=l.id
                LEFT JOIN public.crm_deals d ON d.id=l.converted_deal_id AND d.organization_id=l.organization_id AND d.deleted_at IS NULL
                WHERE l.organization_id=@org AND l.id>@cursor AND l.deleted_at IS NULL
                    AND COALESCE(st.data_json->>'archived','false')<>'true'
                    AND (l.created_at<=@old OR st.data_json->'proposalReminder'->>'dueAt' IS NOT NULL
                        OR st.data_json->>'lastResponseAt' IS NOT NULL)
                    AND "+CrmDirectoryWrites.BranchScope("crm_leads","l")+@"
                ORDER BY l.id LIMIT 100 FOR UPDATE OF l,st SKIP LOCKED",
                ("org",NpgsqlDbType.Integer,org),("scope_branch",NpgsqlDbType.Integer,settings.BranchId),
                ("cursor",NpgsqlDbType.Integer,cursor),("old",NpgsqlDbType.TimestampTz,now.AddDays(-7)));
            DataTable batch;
            using(var rows=await query.ExecuteReaderAsync(cancellation))
                batch=await Table(rows,cancellation);
            if (batch.Rows.Count==0)
                break;
            foreach(DataRow lead in batch.Rows)
            {
                cursor=(int)lead["id"];
                if (lead["reminder_branch"] is not int branch)
                    continue;
                var details=ReadDetails(lead);
                bool changed=false;
                foreach(var reminder in SalesReminders(lead,details,manager,now))
                {
                    if (managerAlerts+proposalAlerts+nurtureAlerts>=notificationLimit)
                        break;
                    if (reminder.Recipient is not int recipient ||
                        !await CanNotifyLeadReminderRecipientAsync(db,tx,org,branch,recipient,lead,cancellation))
                        continue;
                    await NotifyLeadOwnerAsync(db,tx,org,branch,cursor,lead,actor.Id,reminder.Kind,reminder.Title,
                        Text(lead,"full_name")+": "+reminder.Title,cancellation,recipient);
                    details[reminder.Key]=reminder.Value;
                    changed=true;
                    switch(reminder.Kind)
                    {
                        case "lead_no_response": managerAlerts++; break;
                        case "lead_proposal_due": proposalAlerts++; break;
                        case "lead_nurture_due": nurtureAlerts++; break;
                    }
                }
                if (changed)
                {
                    await WriteState(db,tx,org,cursor,details,Text(lead,"state_revision"),cancellation);
                    await CrmDirectoryWrites.Audit(db,tx,"crm_leads",org,cursor,actor.Id,"UPDATE",cancellation,
                        "Lead sales process reminders recorded");
                }
            }
        }
        tx.Commit();
        return new(true,managerAlerts,proposalAlerts,nurtureAlerts);
    }

    private static IEnumerable<SalesReminder> SalesReminders(DataRow lead,Dictionary<string,object?> details,int? manager,DateTime now)
    {
        string dealStatus=Text(lead,"reminder_deal_status").ToLowerInvariant();
        bool closed=lead["status"] is "Lost" || dealStatus is "won" or "lost";
        int? owner=lead["owner_user_id"] as int?;
        DateTime response=ReminderDate(details.TryGetValue("lastResponseAt",out var recent)?recent:null)
            ?? lead["created_at"] as DateTime? ?? now;
        string cycle=ReminderCycle(response);
        if (!closed && now>=response.AddDays(7) && !RecordedCycle(details,"managerAlertCycle",cycle))
            yield return new("managerAlertCycle",cycle,manager,"No response for 7 days","lead_no_response");
        if (!closed && details.TryGetValue("proposalReminder",out var proposal) && proposal is JsonElement proposalState &&
            proposalState.ValueKind==JsonValueKind.Object &&
            Nested(proposal,"sent") is not JsonElement {ValueKind:JsonValueKind.True} &&
            ReminderDate(Nested(proposal,"dueAt")) is DateTime due && now>=due)
        {
            var next=proposalState.EnumerateObject().ToDictionary(item=>item.Name,item=>(object?)item.Value.Clone());
            next["sent"]=true;
            yield return new("proposalReminder",next,owner,"Proposal follow-up due","lead_proposal_due");
        }
        if (dealStatus=="won" || !details.TryGetValue("nurtureConsent",out var consent) ||
            Nested(consent,"allowed") is not JsonElement {ValueKind:JsonValueKind.True})
            yield break;
        DateTime anchored=ReminderDate(Nested(consent,"recordedAt")) is DateTime recorded&&recorded>response?recorded:response;
        string nurtureCycle=ReminderCycle(anchored);
        if (now>=anchored.AddDays(30) && !RecordedCycle(details,"nurtureAlertCycle",nurtureCycle))
            yield return new("nurtureAlertCycle",nurtureCycle,owner,"Nurture follow-up due (permission recorded)","lead_nurture_due");
    }

    private static bool RecordedCycle(Dictionary<string,object?> details,string field,string current) =>
        details.TryGetValue(field,out var value) && ReminderDate(value) is DateTime date && ReminderCycle(date)==current;

    private static DateTime? ReminderDate(object? value) =>
        DateTimeOffset.TryParse(value?.ToString(),CultureInfo.InvariantCulture,DateTimeStyles.AssumeUniversal,out var parsed)
            ?parsed.UtcDateTime:null;

    private static string ReminderCycle(DateTime utc)
    {
        bool fractional=utc.Ticks/10%1000000!=0;
        return utc.ToString(fractional?"yyyy-MM-dd'T'HH:mm:ss.ffffff'+00:00'":"yyyy-MM-dd'T'HH:mm:ss'+00:00'",
            CultureInfo.InvariantCulture);
    }
}
