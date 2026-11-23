using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record LeadPreview(DataRow Details,DataTable History,LeadSignals Signals,bool CanWrite,bool CanScore);

internal static partial class LeadStore
{
    internal static async Task<DataTable> LeadHistoryAsync(int lead,bool potential,CancellationToken cancellation)
    {
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor=await CrmDirectoryWrites.RequireCrmActorAsync(settings,db,tx,cancellation,"leads");
        return await ReadLeadHistoryAsync(db,tx,settings,actor,lead,potential,cancellation);
    }

    internal static async Task<LeadPreview> LeadPreviewAsync(int lead,bool potential,CancellationToken cancellation)
    {
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor=await CrmDirectoryWrites.RequireCrmActorAsync(settings,db,tx,cancellation,"leads");
        using var query=Cmd(db,tx,@"SELECT l.id,l.xmin::text AS revision,COALESCE(state.xmin::text,'') AS state_revision,
            l.full_name,l.company_name,l.status,l.source,l.rating,l.lead_score,l.lead_score_mode,l.is_converted,
            l.created_at,l.last_contacted_at,state.data_json->>'lastActivityAt' AS last_activity_text,
            state.data_json->>'scoreOverrideReason' AS score_override_reason,
            l.email,CASE WHEN trim(l.phone) LIKE '+%' OR l.phone_country_code IS NULL THEN l.phone
                      ELSE l.phone_country_code||' '||l.phone END AS phone,
            l.next_follow_up_at AT TIME ZONE 'UTC' AS follow_up,
            COALESCE(NULLIF(person.display_name,''),'User '||l.owner_user_id::text,'Unassigned') AS owner,
            state.data_json->'qualification'->>'need' AS need,("+CrmDirectoryWrites.BranchScope("crm_leads","l")+@") AS owning_scope
            FROM public.crm_leads l
            LEFT JOIN public.crm_lead_operating_states state ON state.organization_id=l.organization_id AND state.lead_id=l.id
            LEFT JOIN public.common_people person ON person.organization_id=l.organization_id AND person.user_id=l.owner_user_id
            WHERE "+PreviewScope,
            ("org",NpgsqlDbType.Integer,settings.OrganizationId),("lead",NpgsqlDbType.Integer,lead),
            ("scope_branch",NpgsqlDbType.Integer,settings.BranchId),("potential",NpgsqlDbType.Boolean,potential));
        DataRow details;
        using (var reader=await query.ExecuteReaderAsync(cancellation))
        {
            var rows=await Table(reader,cancellation);
            if (rows.Rows.Count!=1)
                throw new InvalidOperationException("This Lead is unavailable in the current company and branch.");
            details=rows.Rows[0];
        }
        bool canWrite=false;
        bool canScore=false;
        if (actor.CanWriteBranch && details["owning_scope"] is true)
        {
            try
            {
                await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"leads","edit");
                canWrite=true;
                await RequireLeadScoreWriteAsync(db,tx,settings,actor);
                canScore=true;
            }
            catch (UnauthorizedAccessException) { }
        }
        var policy=await ReadPolicy(db,tx,settings.OrganizationId,cancellation);
        return new(details,await ReadLeadHistoryAsync(db,tx,settings,actor,lead,potential,cancellation),
            LeadSignals.Evaluate(details,policy,DateTime.UtcNow),canWrite,canScore);
    }

    private static readonly string PreviewScope=@"l.organization_id=@org AND l.id=@lead AND l.deleted_at IS NULL
        AND COALESCE(state.data_json->>'archived','false')<>'true'
        AND (COALESCE(state.data_json->>'recordType','Lead')='Potential')=@potential
        AND "+CrmDirectoryWrites.BranchScope("crm_leads","l",includeShares:true);

    private static async Task<DataTable> ReadLeadHistoryAsync(NpgsqlConnection db,NpgsqlTransaction tx,
        DesktopDatabaseSettings settings,DesktopActor actor,int lead,bool potential,CancellationToken cancellation)
    {
        bool communications=await MayReadLeadCommunicationsAsync(db,tx,settings,actor);
        using var query=Cmd(db,tx,@"WITH scoped AS (
            SELECT l.id,l.organization_id FROM public.crm_leads l
            LEFT JOIN public.crm_lead_operating_states state ON state.organization_id=l.organization_id AND state.lead_id=l.id
            WHERE "+PreviewScope+@"
        ), timeline AS (
            SELECT e.id,e.occurred_at,e.event_type,e.title,e.description,e.actor_user_id,
                e.metadata_json->>'durationHours' AS duration,e.metadata_json->'mentionIds' AS mentions,'crm' AS source
            FROM public.crm_timeline_events e JOIN scoped l ON l.id=e.record_id AND l.organization_id=e.organization_id
            WHERE e.record_type='lead'
            ORDER BY e.occurred_at DESC NULLS LAST,e.id DESC LIMIT 100
        ), communication AS (
            SELECT e.id,e.created_at AS occurred_at,e.channel||'_'||e.event_type AS event_type,
                COALESCE(NULLIF(e.subject,''),e.channel||': '||e.event_type) AS title,e.summary AS description,
                e.actor_user_id,NULL::text AS duration,NULL::json AS mentions,'communication' AS source
            FROM public.communication_timeline_events e JOIN scoped l ON l.id=e.record_id AND l.organization_id=e.organization_id
            WHERE @communication AND e.record_type='lead'
              AND (@scope_branch IS NULL OR NOT EXISTS (SELECT 1 FROM public.suite_branch_ownership b
                  WHERE b.company_id=e.organization_id AND b.resource_table='communication_timeline_events'
                    AND b.resource_key=e.id::text AND b.branch_id<>@scope_branch)
                  OR EXISTS (SELECT 1 FROM public.suite_branch_record_shares share
                  WHERE share.company_id=e.organization_id AND share.resource_table='communication_timeline_events'
                    AND share.resource_key=e.id::text AND share.branch_id=@scope_branch))
            ORDER BY e.created_at DESC NULLS LAST,e.id DESC LIMIT 100
        ), conversion AS (
            SELECT c.id,c.converted_at AS occurred_at,'conversion' AS event_type,'Lead converted' AS title,c.notes AS description,
                c.converted_by_user_id AS actor_user_id,NULL::text AS duration,NULL::json AS mentions,'conversion' AS source
            FROM public.crm_lead_conversion_logs c JOIN scoped l ON l.id=c.lead_id AND l.organization_id=c.organization_id
            WHERE c.conversion_status='completed' AND c.notes='Converted in Business Suite Desktop'
            ORDER BY c.converted_at DESC NULLS LAST,c.id DESC LIMIT 100
        )
        SELECT event.occurred_at AT TIME ZONE 'UTC' AS occurred,replace(event.event_type,'_',' ') AS kind,
            event.title,event.description,COALESCE(NULLIF(person.display_name,''),'User '||event.actor_user_id::text,'System') AS actor,
            event.duration,recipients.names AS recipients
        FROM (SELECT * FROM timeline UNION ALL SELECT * FROM communication UNION ALL SELECT * FROM conversion) event
        LEFT JOIN LATERAL (SELECT p.display_name FROM public.common_people p WHERE p.organization_id=@org
            AND p.user_id=event.actor_user_id ORDER BY p.id LIMIT 1) person ON true
        LEFT JOIN LATERAL (
            SELECT string_agg(COALESCE(NULLIF(p.display_name,''),'User '||r.id),', ' ORDER BY r.position) AS names
            FROM json_array_elements_text(CASE WHEN event.event_type='team_note' AND json_typeof(event.mentions)='array'
                THEN event.mentions ELSE '[]'::json END) WITH ORDINALITY r(id,position)
            LEFT JOIN public.common_people p ON p.organization_id=@org AND p.user_id::text=r.id
        ) recipients ON true
        ORDER BY event.occurred_at DESC NULLS LAST,event.source,event.id DESC",
            ("org",NpgsqlDbType.Integer,settings.OrganizationId),("lead",NpgsqlDbType.Integer,lead),
            ("scope_branch",NpgsqlDbType.Integer,settings.BranchId),("potential",NpgsqlDbType.Boolean,potential),
            ("communication",NpgsqlDbType.Boolean,communications));
        using var rows=await query.ExecuteReaderAsync(cancellation);
        return await Table(rows,cancellation);
    }

    private static async Task<bool> MayReadLeadCommunicationsAsync(NpgsqlConnection db,NpgsqlTransaction tx,
        DesktopDatabaseSettings settings,DesktopActor actor)
    {
        try
        {
            var grant=await DesktopModuleAccess.RequireAsync(db,tx,settings.OrganizationId,settings.BranchId??0,actor,
                "communication","view","communication_view","communication_email_send");
            return actor.IsSuperuser || grant.Scope=="organization" || (settings.BranchId.HasValue && grant.Scope=="branch");
        }
        catch(UnauthorizedAccessException)
        {
            return false;
        }
    }
}
