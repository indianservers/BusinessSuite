using System.Data;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using Npgsql;

namespace Business_Suite;

internal sealed record CampaignDeliveryRow(DateTime? Recorded, string Recipient, string Email, string Channel,
    string Status, string Note);
internal sealed record CampaignChangeRow(DateTime? Recorded, string Change, int? ActorId, string Name);
internal sealed record CampaignHistory(List<CampaignDeliveryRow> Deliveries, List<CampaignChangeRow> Changes, bool DeliveryAvailable);

internal sealed partial class CommunicationDraftRepository
{
    internal async Task<CampaignHistory> CampaignHistoryAsync(int id)
    {
        int branch = RequireBranch();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        using (var readOnly = new NpgsqlCommand("SET TRANSACTION READ ONLY", db, tx))
            await readOnly.ExecuteNonQueryAsync();
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        var grant = await CampaignGrantAsync(db, tx, branch, actor, "view");
        await ReadCampaignAsync(db, tx, branch, actor.Id, grant.Scope, id, false);
        var changes = await ReadCampaignChangesAsync(db, tx, branch, actor.Id, id);
        try
        {
            var deliveries = await ReadCampaignDeliveriesAsync(db, tx, branch, actor, id);
            return new(deliveries, changes, true);
        }
        catch (UnauthorizedAccessException)
        {
            return new([], changes, false);
        }
    }

    private async Task<List<CampaignChangeRow>> ReadCampaignChangesAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        int branch, int actor, int campaign)
    {
        using var command = Scoped(@"SELECT a.created_at,a.reason,a.actor_id,coalesce(a.details->>'name','')
            FROM public.suite_branch_audit a WHERE a.company_id=@company AND a.operation='communication.campaign'
              AND a.details->>'campaign_id'=@campaign::text AND a.details->>'branch_id'=@branch::text
              AND a.reason IN ('create','edit','cancel') ORDER BY a.id DESC LIMIT 200", db, tx, branch, actor);
        command.Parameters.AddWithValue("campaign", campaign);
        using var reader = await command.ExecuteReaderAsync();
        var result = new List<CampaignChangeRow>();
        while (await reader.ReadAsync())
        {
            string action = reader.GetString(1) switch
            {
                "create" => "Created",
                "edit" => "Edited",
                _ => "Cancelled"
            };
            result.Add(new(reader.IsDBNull(0) ? null : reader.GetDateTime(0).ToLocalTime(), action,
                reader.IsDBNull(2) ? null : reader.GetInt32(2), reader.GetString(3)));
        }
        return result;
    }

    private async Task<List<CampaignDeliveryRow>> ReadCampaignDeliveriesAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        int branch, DesktopActor actor, int campaign)
    {
        CrmDirectoryWrites.RequireCrmAccess(actor);
        var crm = await DesktopModuleAccess.RequireAsync(db, tx, settings.OrganizationId, branch, actor,
            "crm", "view", "crm_view", "crm_manage", "crm_admin");
        var logs = await DesktopModuleAccess.RequireAsync(db, tx, settings.OrganizationId, branch, actor,
            "communication", "view", "communication_logs_view", "communication_view");
        if (crm.Scope != "organization" || logs.Scope is not ("organization" or "own"))
            throw new UnauthorizedAccessException("Campaign delivery history requires access to CRM recipients in the selected branch.");
        using var command = Scoped(@"WITH visible AS (" + RecipientScope + @"),
          members AS (
            SELECT m.id,m.record_type,m.record_id,m.email,m.status,m.created_at,r.name
            FROM public.communication_campaign_members m
            JOIN visible r ON r.id=m.record_id AND r.kind=m.record_type AND r.kind IN ('lead','contact')
            WHERE m.campaign_id=@campaign AND m.organization_id=@company AND lower(btrim(m.email))=lower(btrim(r.email))
                AND NOT EXISTS (SELECT 1 FROM public.suite_branch_ownership b
                    WHERE b.resource_table='communication_campaign_members' AND b.resource_key=m.id::text
                      AND (b.company_id<>@company OR b.branch_id<>@branch))
          ), attempts AS (
            SELECT s.id,s.member_id,s.status,s.created_at,s.error_message IS NOT NULL AS has_error
            FROM public.communication_campaign_sends s JOIN members m ON m.id=s.member_id
            WHERE s.organization_id=@company AND s.campaign_id=@campaign
              AND NOT EXISTS (SELECT 1 FROM public.suite_branch_ownership b
                    WHERE b.resource_table='communication_campaign_sends' AND b.resource_key=s.id::text
                      AND (b.company_id<>@company OR b.branch_id<>@branch))
              AND (s.email_message_id IS NULL OR EXISTS (
                SELECT 1 FROM public.communication_email_messages message
                WHERE message.id=s.email_message_id AND message.organization_id=@company
                  AND message.related_record_type=m.record_type AND message.related_record_id=m.record_id
                  AND lower(btrim(message.to_email))=lower(btrim(m.email))
                  AND NOT EXISTS (SELECT 1 FROM public.suite_branch_ownership b
                    WHERE b.resource_table='communication_email_messages' AND b.resource_key=message.id::text
                      AND (b.company_id<>@company OR b.branch_id<>@branch))))
          ), events AS (
            SELECT coalesce(s.created_at,m.created_at) AS recorded,m.name,m.email,
              CASE WHEN s.id IS NULL THEN 'Campaign member' ELSE 'Direct send' END AS origin,
              coalesce(s.status,m.status,'') AS status,
              coalesce(s.has_error,false) AS has_error,NULL::text AS event_key
            FROM members m LEFT JOIN attempts s ON s.member_id=m.id
            UNION ALL
            SELECT coalesce(o.accepted_at,o.created_at),r.name,o.recipient,'Scheduled worker',o.status,o.error IS NOT NULL,o.event_key
            FROM public.email_outbox o
            JOIN LATERAL (SELECT name FROM visible
              WHERE kind IN ('lead','contact') AND lower(btrim(email))=lower(btrim(o.recipient))
              ORDER BY id DESC LIMIT 1) r ON true
            WHERE o.organization_id=@company AND o.module='campaign'
              AND starts_with(o.event_key,'campaign:'||@campaign::text||':')
              AND NOT EXISTS (SELECT 1 FROM public.suite_branch_ownership b
                    WHERE b.resource_table='email_outbox' AND b.resource_key=o.id::text
                      AND (b.company_id<>@company OR b.branch_id<>@branch))
          )
          SELECT recorded,name,email,origin,status,has_error,event_key FROM events WHERE status<>''
          ORDER BY recorded DESC NULLS LAST, email, origin LIMIT 200", db, tx, branch, actor.Id);
        command.Parameters.AddWithValue("campaign", campaign);
        using var reader = await command.ExecuteReaderAsync();
        var rows = new List<CampaignDeliveryRow>();
        while (await reader.ReadAsync())
        {
            string email = reader.GetString(2);
            if (!reader.IsDBNull(6) && !string.Equals(reader.GetString(6), OutboxEventKey(campaign, email), StringComparison.Ordinal))
                continue;
            string status = reader.GetString(4);
            string origin = reader.GetString(3);
            string note = status is "sent" or "accepted" ? "Recipient delivery is unconfirmed."
                : reader.GetBoolean(5) ? "A delivery error was recorded."
                : origin == "Campaign member" ? "Member status only." : "";
            rows.Add(new(reader.IsDBNull(0) ? null : reader.GetDateTime(0).ToLocalTime(), reader.GetString(1), email,
                origin, status, note));
        }
        return rows;
    }

    private static string OutboxEventKey(int campaign, string address)
    {
        using var sha = SHA256.Create();
        var hash = BitConverter.ToString(sha.ComputeHash(Encoding.UTF8.GetBytes(address.ToLowerInvariant())))
            .Replace("-", "").ToLowerInvariant();
        return "campaign:" + campaign.ToString(CultureInfo.InvariantCulture) + ":" + hash;
    }
}
