using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class CrmDealRepository
{
    internal async Task<List<DealCaptureChoice>> NoteMentionOptionsAsync(int dealId,CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor=await settings.RequireActorAsync(db,tx,cancellation);
        await RequireNoteWriterAsync(db,tx,actor);
        await LockableDealAsync(db,tx,dealId,false,cancellation,requireOpen:false);
        return await EligibleNoteRecipientsAsync(db,tx,actor.Id,[],cancellation);
    }

    private async Task<List<DealCaptureChoice>> EligibleNoteRecipientsAsync(NpgsqlConnection db,NpgsqlTransaction tx,int author,
        int[] ids,CancellationToken cancellation)
    {
        using var query=Query(db,tx,@"SELECT u.id,COALESCE(NULLIF(p.display_name,''),u.email) AS name,
            COALESCE(u.is_superuser,false) AS superuser,COALESCE(m.is_admin,false) AS company_admin
            FROM public.users u
            LEFT JOIN public.common_people p ON p.user_id=u.id
            LEFT JOIN public.suite_access_memberships m ON m.user_id=u.id AND m.company_id=@org
            WHERE u.is_active AND u.id<>@author AND (cardinality(@ids)=0 OR u.id=ANY(@ids))
                AND (
                    (m.active AND (m.is_admin OR u.is_superuser))
                    OR (m.id IS NULL AND p.organization_id=@org AND u.is_superuser)
                ) AND (p.organization_id IS NULL OR p.organization_id=@org)
            ORDER BY name,u.id",
            ("author",NpgsqlDbType.Integer,author),("ids",NpgsqlDbType.Array|NpgsqlDbType.Integer,ids));
        DataTable candidates=await ReadAsync(query,cancellation);
        var choices=new List<DealCaptureChoice>();
        foreach (DataRow candidate in candidates.Rows)
        {
            var recipient=new DesktopActor((int)candidate["id"],(bool)candidate["superuser"],(bool)candidate["company_admin"],false);
            if (await CanReadNotesAsync(db,tx,recipient))
                choices.Add(new(recipient.Id,(string)candidate["name"]));
        }
        return choices;
    }

    private async Task WriteNoteMentionsAsync(NpgsqlConnection db,NpgsqlTransaction tx,int author,int deal,int branch,
        string title,int note,int[] recipients,CancellationToken cancellation)
    {
        using var command=Query(db,tx,@"WITH recipients AS (SELECT unnest(@recipients) AS user_id),
            notes AS (
                INSERT INTO public.crm_note_mentions (organization_id,note_id,mentioned_user_id,mentioned_by,entity_type,entity_id)
                SELECT @org,@note,user_id,@actor,'deal',@deal FROM recipients RETURNING id
            ), notifications AS (
                INSERT INTO public.notifications (company_id,user_id,title,message,module,event_type,related_entity_type,
                    related_entity_id,action_url,priority,channels,is_read)
                SELECT @org,user_id,'You were mentioned in CRM',@message,'crm','crm_mention','deal',
                    @deal,@url,'normal','[""in_app""]'::json,false FROM recipients RETURNING id
            ) INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
            SELECT 'crm_note_mentions',id::text,@org,@branch,'desktop-crm' FROM notes
            UNION ALL SELECT 'notifications',id::text,@org,@branch,'desktop-crm' FROM notifications",
            ("recipients",NpgsqlDbType.Array|NpgsqlDbType.Integer,recipients),("deal",NpgsqlDbType.Integer,deal),
            ("note",NpgsqlDbType.Integer,note),("actor",NpgsqlDbType.Integer,author),("branch",NpgsqlDbType.Integer,branch),
            ("url",NpgsqlDbType.Text,$"/crm/deals/{deal}"),("message",NpgsqlDbType.Text,$"You were mentioned on {title}."));
        await command.ExecuteNonQueryAsync(cancellation);
    }
}
