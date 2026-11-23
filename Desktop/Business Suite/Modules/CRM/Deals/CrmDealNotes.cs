using System.Data;
using System.Globalization;
using System.Text.Json;
using System.Text.RegularExpressions;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class CrmDealRepository
{
    internal const int NoteLimit=10000;
    private static readonly Regex NoteMention=new(@"@\[([^\]]+)\]\(user:(\d+)\)",RegexOptions.CultureInvariant);
    private const string NoteBranchScope=@"(@scope_branch IS NULL OR NOT EXISTS (
        SELECT 1 FROM public.suite_branch_ownership o WHERE o.company_id=n.organization_id
          AND o.resource_table='crm_notes' AND o.resource_key=n.id::text AND o.branch_id<>@scope_branch))";

    private async Task<bool> CanReadNotesAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor)
    {
        if (!actor.IsSuperuser && !actor.IsCompanyAdmin)
            return false;
        try
        {
            await RequireVisibilityAsync(db,tx,actor,["crm_view","crm_manage","crm_admin"]);
            return true;
        }
        catch(UnauthorizedAccessException) { return false; }
    }

    private async Task<DataTable> ReadDealNotesAsync(NpgsqlConnection db,NpgsqlTransaction tx,int id,bool allowed,
        CancellationToken cancellation)
    {
        using var query=Query(db,tx,@"SELECT n.id,n.xmin::text AS revision,n.created_at,COALESCE(n.is_pinned,false) AS is_pinned,n.body,
            CASE WHEN n.author_user_id IS NULL THEN 'Unknown author' ELSE COALESCE(u.email,'User #'||n.author_user_id::text) END AS author
            FROM public.crm_notes n LEFT JOIN public.users u ON u.id=n.author_user_id AND EXISTS (
                SELECT 1 FROM public.common_people p WHERE p.user_id=u.id AND p.organization_id=@org)
            WHERE @allow AND n.organization_id=@org AND n.deal_id=@id AND n.deleted_at IS NULL AND "+NoteBranchScope+@"
            ORDER BY n.is_pinned DESC NULLS LAST,n.created_at DESC NULLS LAST,n.id DESC LIMIT 100",
            ("allow",NpgsqlDbType.Boolean,allowed),("id",NpgsqlDbType.Integer,id));
        return await ReadAsync(query,cancellation);
    }

    internal async Task<int> AddDealNoteAsync(int dealId,string input,CancellationToken cancellation)
    {
        string body=ValidateNoteBody(input);
        var ids=ParseNoteRecipients(body);
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await RequireNoteWriterAsync(db,tx,actor);
        var deal=await LockableDealAsync(db,tx,dealId,true,cancellation,requireOpen:false);
        int branch=(int)deal["owning_branch"];
        ids.Remove(actor.Id);
        if (ids.Count>0)
        {
            var visible=await EligibleNoteRecipientsAsync(db,tx,actor.Id,ids.ToArray(),cancellation);
            if (visible.Count!=ids.Count)
                throw new InvalidOperationException("One or more mention recipients are unavailable for CRM notes in this branch.");
        }
        using var insert=Query(db,tx,@"INSERT INTO public.crm_notes (organization_id,deal_id,author_user_id,body,is_internal,is_pinned,
            created_by_user_id,updated_by_user_id)
            VALUES (@org,@deal,@actor,@body,true,false,@actor,@actor) RETURNING id",
            ("deal",NpgsqlDbType.Integer,dealId),("actor",NpgsqlDbType.Integer,actor.Id),("body",NpgsqlDbType.Text,body));
        int id=(int)(await insert.ExecuteScalarAsync(cancellation))!;
        string metadata=JsonSerializer.Serialize(new {sourceEntity="notes",sourceId=id});
        using var effects=Query(db,tx,@"WITH activity AS (
            INSERT INTO public.crm_activities (organization_id,branch_id,owner_user_id,entity_type,entity_id,deal_id,
                activity_type,title,subject,body,description,metadata_json,status,activity_date,created_by_user_id,updated_by_user_id)
            VALUES (@org,@branch,@actor,'deal',@deal,@deal,'note','Note added','Note added',@body,@body,@metadata,'Completed',now(),@actor,@actor)
            RETURNING id
        ), ownership AS (
            INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
            SELECT 'crm_activities',id::text,@org,@branch,'desktop-crm' FROM activity
            UNION ALL SELECT 'crm_notes',@id::text,@org,@branch,'desktop-crm'
        ), last_activity AS (
            UPDATE public.crm_deals SET last_activity_at=now(),updated_at=now(),updated_by_user_id=@actor,version=version+1
            WHERE organization_id=@org AND id=@deal
        ) INSERT INTO public.crm_timeline_events (organization_id,record_type,record_id,event_type,title,description,
            metadata_json,actor_user_id,occurred_at)
          VALUES (@org,'deal',@deal,'note','Note added',@body,@metadata,@actor,now())",
            ("id",NpgsqlDbType.Integer,id),("deal",NpgsqlDbType.Integer,dealId),("branch",NpgsqlDbType.Integer,branch),
            ("actor",NpgsqlDbType.Integer,actor.Id),("body",NpgsqlDbType.Text,body),("metadata",NpgsqlDbType.Json,metadata));
        await effects.ExecuteNonQueryAsync(cancellation);
        if (ids.Count>0)
            await WriteNoteMentionsAsync(db,tx,actor.Id,dealId,branch,(string)deal["name"],id,ids.ToArray(),cancellation);
        await CrmDirectoryWrites.Audit(db,tx,"notes",settings.OrganizationId,id,actor.Id,"CREATE",cancellation);
        tx.Commit();
        return id;
    }

    internal static string RenderNote(string body)=>NoteMention.Replace(body,"@$1");

    private static string ValidateNoteBody(string input)
    {
        string body=input.Trim();
        if (body.Length<1 || body.Length>NoteLimit)
            throw new ArgumentException($"Enter a note of up to {NoteLimit:N0} characters.");
        return body;
    }

    private static HashSet<int> ParseNoteRecipients(string body)
    {
        var ids=new HashSet<int>();
        foreach (Match mention in NoteMention.Matches(body))
        {
            if (!int.TryParse(mention.Groups[2].Value,NumberStyles.None,CultureInfo.InvariantCulture,out int recipient) || recipient<=0)
                throw new ArgumentException("Select valid CRM mention recipients.");
            ids.Add(recipient);
        }
        if (ids.Count>20)
            throw new ArgumentException("Select up to 20 recipients for one note.");
        return ids;
    }

    private async Task RequireNoteWriterAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor,string action="create")
    {
        if (!actor.IsSuperuser || !actor.CanWriteBranch || !settings.BranchId.HasValue)
            throw new UnauthorizedAccessException("Add Deal note requires a Suite superuser in a writable branch.");
        await RequireDealsAsync(db,tx,actor,false);
        var access=await DesktopModuleAccess.RequireAsync(db,tx,settings.OrganizationId,settings.BranchId.Value,
            actor,"crm",action,["crm_manage","crm_admin"]);
        if (access.Scope is not ("branch" or "organization"))
            throw new UnauthorizedAccessException("Add Deal note requires branch-wide or organization-wide CRM access.");
    }
}
