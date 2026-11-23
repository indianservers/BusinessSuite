using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class CrmDealRepository
{
    internal Task SaveDealCallAsync(int deal,int call,string revision,DealCallDraft draft,CancellationToken cancellation)=>
        ChangeDealCallAsync(deal,call,revision,ValidateCallDraft(draft),cancellation);

    internal Task ArchiveDealCallAsync(int deal,int call,string revision,CancellationToken cancellation)=>
        ChangeDealCallAsync(deal,call,revision,null,cancellation);

    private async Task ChangeDealCallAsync(int deal,int call,string revision,DealCallDraft? draft,CancellationToken cancellation)
    {
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await RequireDealActivityAccessAsync(db,tx,actor,draft is null?"delete":"edit");
        await LockableDealAsync(db,tx,deal,true,cancellation,requireOpen:false);
        string values=draft is null?"deleted_at=now()":@"direction=@direction,phone_number=@phone,phone_number_country_code=@code,
            call_time=@time,duration_seconds=@duration,outcome=NULLIF(@outcome,''),notes=NULLIF(@notes,'')";
        using var update=Query(db,tx,@"WITH original AS (
            SELECT c.id,to_jsonb(c) AS old FROM public.crm_call_logs c WHERE c.organization_id=@org
              AND c.deal_id=@deal AND c.id=@call AND c.deleted_at IS NULL AND c.xmin::text=@revision
              AND "+CallBranchScope+@" FOR UPDATE OF c
        ), changed AS (
            UPDATE public.crm_call_logs c SET "+values+@",updated_by_user_id=@actor,updated_at=now()
            FROM original WHERE c.organization_id=@org AND c.id=original.id RETURNING original.old,to_jsonb(c) AS current
        ) INSERT INTO public.audit_logs (organization_id,user_id,actor_authenticated,method,entity_type,entity_id,action,
            description,module,old_values,new_values)
        SELECT @org,@actor,true,'CRM','calls',@call,@action,@reason,'crm',old::text,current::text FROM changed",
            ("deal",NpgsqlDbType.Integer,deal),("call",NpgsqlDbType.Integer,call),("revision",NpgsqlDbType.Text,revision),
            ("actor",NpgsqlDbType.Integer,actor.Id),("direction",NpgsqlDbType.Text,draft?.Direction),("phone",NpgsqlDbType.Text,draft?.Phone),
            ("code",NpgsqlDbType.Text,draft?.CallingCode),("time",NpgsqlDbType.TimestampTz,draft?.CallTime),
            ("duration",NpgsqlDbType.Integer,draft?.Duration),("outcome",NpgsqlDbType.Text,draft?.Outcome),("notes",NpgsqlDbType.Text,draft?.Notes),
            ("action",NpgsqlDbType.Text,draft is null?"DELETE":"UPDATE"),
            ("reason",NpgsqlDbType.Text,draft is null?"CRM Deal call archived":"CRM Deal call revised"));
        if (await update.ExecuteNonQueryAsync(cancellation)!=1)
            throw new InvalidOperationException("This call changed or is unavailable. Refresh and try again.");
        tx.Commit();
    }
}
