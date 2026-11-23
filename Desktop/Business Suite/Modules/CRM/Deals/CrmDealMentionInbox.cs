using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class CrmDealRepository
{
    private static readonly string InboxScope=@"n.company_id=@org AND n.user_id=@actor AND n.module='crm'
        AND (n.event_type='deal.updated' OR (@notes AND n.event_type='crm_mention')) AND n.related_entity_type='deal'
        AND (@scope_branch IS NULL OR NOT EXISTS (
            SELECT 1 FROM public.suite_branch_ownership bo WHERE bo.company_id=@org
                AND bo.resource_table='notifications' AND bo.resource_key=n.id::text AND bo.branch_id<>@scope_branch))
        AND EXISTS (SELECT 1 FROM public.crm_deals d WHERE d.organization_id=@org
            AND d.id=n.related_entity_id AND d.deleted_at IS NULL AND "+CrmDirectoryWrites.BranchScope("crm_deals","d")+")";

    internal async Task<DataTable> MentionInboxAsync(bool unreadOnly,CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor=await settings.RequireActorAsync(db,tx,cancellation);
        bool notes=await RequireInboxAsync(db,tx,actor);
        using var query=Query(db,tx,@"SELECT n.id,n.related_entity_id AS deal_id,n.created_at,n.title,n.message,n.event_type,
            COALESCE(n.is_read,false) AS is_read FROM public.notifications n WHERE "+InboxScope+@"
            AND (NOT @unread OR NOT COALESCE(n.is_read,false))
            ORDER BY n.created_at DESC NULLS LAST,n.id DESC LIMIT 100",
            ("actor",NpgsqlDbType.Integer,actor.Id),("notes",NpgsqlDbType.Boolean,notes),("unread",NpgsqlDbType.Boolean,unreadOnly));
        return await ReadAsync(query,cancellation);
    }

    internal async Task MarkMentionReadAsync(int notificationId,CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        bool notes=await RequireInboxAsync(db,tx,actor);
        using var command=Query(db,tx,@"UPDATE public.notifications n SET is_read=true,
            read_at=CASE WHEN COALESCE(n.is_read,false) THEN n.read_at ELSE now() END
            WHERE n.id=@id AND "+InboxScope+" RETURNING id",
            ("id",NpgsqlDbType.Integer,notificationId),("actor",NpgsqlDbType.Integer,actor.Id),("notes",NpgsqlDbType.Boolean,notes));
        if (await command.ExecuteScalarAsync(cancellation) is null)
            throw new InvalidOperationException("This alert is unavailable in your inbox.");
        tx.Commit();
    }

    private async Task<bool> RequireInboxAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor)
    {
        await RequireDealsAsync(db,tx,actor,false);
        return await CanReadNotesAsync(db,tx,actor);
    }
}
