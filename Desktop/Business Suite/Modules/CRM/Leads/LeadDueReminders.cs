using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record LeadReminderResult(int Sent,int Skipped,int Examined);

internal static partial class LeadStore
{
    internal static async Task<LeadReminderResult> ProcessDueLeadRemindersAsync(CancellationToken cancellation)
    {
        const int limit=200;
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await RequireLeadSettingsAdminAsync(db,tx,settings,actor);
        int org=settings.OrganizationId;
        using var select=Cmd(db,tx,@"SELECT l.*,a.id AS activity_id,a.owner_user_id AS reminder_owner,a.subject AS reminder_subject,
                COALESCE((SELECT o.branch_id FROM public.suite_branch_ownership o WHERE o.company_id=@org
                    AND o.resource_table='crm_leads' AND o.resource_key=l.id::text),l.branch_id) AS reminder_branch
            FROM public.crm_activities a JOIN public.crm_leads l ON l.id=a.lead_id AND l.organization_id=a.organization_id
            JOIN public.users u ON u.id=a.owner_user_id AND u.is_active
            LEFT JOIN public.crm_lead_operating_states st ON st.lead_id=l.id AND st.organization_id=l.organization_id
            LEFT JOIN public.crm_deals d ON d.id=l.converted_deal_id AND d.organization_id=l.organization_id AND d.deleted_at IS NULL
            WHERE a.organization_id=@org AND a.deleted_at IS NULL AND l.deleted_at IS NULL AND l.status<>'Lost'
                AND (d.id IS NULL OR lower(d.status) NOT IN ('won','lost'))
                AND COALESCE(st.data_json->>'archived','false')<>'true'
                AND a.status='Pending' AND a.due_date<=now()
                AND a.metadata_json->>'followUpReminderAt' IS NULL
                AND COALESCE(a.metadata_json->>'salesAutomation','')<>'proposal'
                AND "+CrmDirectoryWrites.BranchScope("crm_leads","l")+@" AND "+LeadActivityScope(false)+@"
            ORDER BY a.due_date,a.id LIMIT @limit
            FOR UPDATE OF a SKIP LOCKED FOR SHARE OF l SKIP LOCKED",
            ("org",NpgsqlDbType.Integer,org),("scope_branch",NpgsqlDbType.Integer,settings.BranchId),
            ("limit",NpgsqlDbType.Integer,limit));
        System.Data.DataTable due;
        using(var rows=await select.ExecuteReaderAsync(cancellation))
            due=await Table(rows,cancellation);
        int sent=0;
        string now=DateTime.UtcNow.ToString("O");
        foreach(System.Data.DataRow row in due.Rows)
        {
            if (row["reminder_branch"] is not int branch || row["reminder_owner"] is not int owner)
                continue;
            if (!await CanNotifyLeadReminderRecipientAsync(db,tx,org,branch,owner,row,cancellation))
                continue;
            int lead=(int)row["id"];
            int activity=(int)row["activity_id"];
            await NotifyLeadOwnerAsync(db,tx,org,branch,lead,row,actor.Id,"lead_follow_up_due","Lead follow-up is due",
                Text(row,"full_name")+": "+Text(row,"reminder_subject"),cancellation,owner,"high");
            using var mark=Cmd(db,tx,@"UPDATE public.crm_activities SET metadata_json=(
                    COALESCE(metadata_json::jsonb,'{}'::jsonb)||jsonb_build_object('followUpReminderAt',@stamp))::json
                WHERE organization_id=@org AND id=@activity",
                ("org",NpgsqlDbType.Integer,org),("activity",NpgsqlDbType.Integer,activity),("stamp",NpgsqlDbType.Text,now));
            await mark.ExecuteNonQueryAsync(cancellation);
            await CrmDirectoryWrites.Audit(db,tx,"crm_activities",org,activity,actor.Id,"UPDATE",cancellation,
                "Lead follow-up reminder recorded");
            sent++;
        }
        tx.Commit();
        return new(sent,due.Rows.Count-sent,due.Rows.Count);
    }

    private static async Task<bool> CanNotifyLeadReminderRecipientAsync(NpgsqlConnection db,NpgsqlTransaction tx,
        int org,int branch,int owner,System.Data.DataRow lead,CancellationToken cancellation)
    {
        var recipients=await LeadOwnerCandidatesAsync(db,tx,org,branch,owner,true,cancellation);
        if (recipients.Count!=1)
            return false;
        try
        {
            await RequireCandidateLeadAccessAsync(db,tx,org,branch,recipients[0].Actor,lead,true);
            return true;
        }
        catch(UnauthorizedAccessException) { return false; }
    }
}
