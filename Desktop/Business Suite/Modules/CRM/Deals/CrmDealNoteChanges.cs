using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class CrmDealRepository
{
    internal Task EditDealNoteAsync(int deal,int note,string revision,string body,CancellationToken cancellation)=>
        ChangeNoteAsync(deal,note,revision,ValidateNoteBody(body),null,cancellation);

    internal Task PinDealNoteAsync(int deal,int note,string revision,bool pinned,CancellationToken cancellation)=>
        ChangeNoteAsync(deal,note,revision,null,pinned,cancellation);

    internal Task ArchiveDealNoteAsync(int deal,int note,string revision,CancellationToken cancellation)=>
        ChangeNoteAsync(deal,note,revision,null,null,cancellation);

    private async Task ChangeNoteAsync(int deal,int note,string revision,string? body,bool? pinned,CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        bool archive=body is null && !pinned.HasValue;
        await RequireNoteWriterAsync(db,tx,actor,archive?"delete":"edit");
        await LockableDealAsync(db,tx,deal,true,cancellation,requireOpen:false);
        using var lookup=Query(db,tx,@"SELECT n.body FROM public.crm_notes n WHERE n.organization_id=@org AND n.deal_id=@deal
            AND n.id=@id AND n.deleted_at IS NULL AND n.xmin::text=@revision AND "+NoteBranchScope+" FOR UPDATE OF n",
            ("deal",NpgsqlDbType.Integer,deal),("id",NpgsqlDbType.Integer,note),("revision",NpgsqlDbType.Text,revision));
        if (await lookup.ExecuteScalarAsync(cancellation) is not string previous)
            throw new InvalidOperationException("The selected note changed or is unavailable. Reopen the deal and try again.");
        if (body is not null && !ParseNoteRecipients(previous).SetEquals(ParseNoteRecipients(body)))
            throw new InvalidOperationException("This edit changes mention recipients. Keep the existing mentions or create a new note.");
        string values=archive?"deleted_at=now()":body is not null?"body=@body":"is_pinned=@pinned";
        using var update=Query(db,tx,@"WITH original AS (
            SELECT n.id,to_jsonb(n) AS old FROM public.crm_notes n WHERE n.organization_id=@org AND n.id=@id
        ), changed AS (
            UPDATE public.crm_notes n SET "+values+@",updated_by_user_id=@actor,updated_at=now()
            FROM original WHERE n.id=original.id AND n.organization_id=@org RETURNING original.old,to_jsonb(n) AS current
        )
        INSERT INTO public.audit_logs (organization_id,user_id,actor_authenticated,method,entity_type,entity_id,action,
            description,module,old_values,new_values)
        SELECT @org,@actor,true,'CRM','notes',@id,@action,@reason,'crm',old::text,current::text FROM changed",
            ("id",NpgsqlDbType.Integer,note),("actor",NpgsqlDbType.Integer,actor.Id),
            ("body",NpgsqlDbType.Text,body),("pinned",NpgsqlDbType.Boolean,pinned),
            ("action",NpgsqlDbType.Text,archive?"DELETE":"UPDATE"),
            ("reason",NpgsqlDbType.Text,archive?"CRM Deal note archived":body is not null?"CRM Deal note edited":pinned==true?"CRM Deal note pinned":"CRM Deal note unpinned"));
        await update.ExecuteNonQueryAsync(cancellation);
        tx.Commit();
    }
}
