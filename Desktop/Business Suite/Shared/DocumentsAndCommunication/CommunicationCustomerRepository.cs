using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record CommunicationCustomerRow(int Id, string Name, string Email, string Phone, bool Active);
internal sealed record CommunicationCustomerNote(string Body, string Author, DateTime? Created,
    string Assignee, DateTime? FollowUp, bool Reminded);
internal sealed record CommunicationNoteAssignee(int Id, string Name);
internal sealed record CommunicationCustomerNotes(List<CommunicationCustomerNote> Rows, bool CanAdd,
    List<CommunicationNoteAssignee> Assignees);
internal sealed record CommunicationCustomerEmail(string Direction, string Subject, string Status,
    DateTime? Recorded, string Body);

internal sealed partial class CommunicationCustomerRepository(DesktopDatabaseSettings settings)
{
    private const string Eligible = @"
        SELECT u.id, COALESCE(NULLIF(person.display_name,''),u.email) AS name
        FROM public.users u
        LEFT JOIN public.common_people person ON person.user_id=u.id
        LEFT JOIN public.suite_access_memberships membership ON membership.user_id=u.id
            AND membership.company_id=@company
        LEFT JOIN public.suite_branch_policies policy ON policy.user_id=u.id AND policy.company_id=@company
        WHERE u.is_active
            AND (membership.active OR (membership.id IS NULL AND
                (person.organization_id=@company OR EXISTS (
                    SELECT 1 FROM public.employees e JOIN public.branches b ON b.id=e.branch_id
                    WHERE e.user_id=u.id AND b.company_id=@company))))
            AND (u.is_superuser OR membership.is_admin OR policy.all_branches OR EXISTS (
                SELECT 1 FROM public.suite_branch_grants g
                WHERE g.user_id=u.id AND g.company_id=@company AND g.branch_id=@branch
            ) OR (COALESCE(policy.use_home_branch,true) AND EXISTS (
                SELECT 1 FROM public.employees e WHERE e.user_id=u.id AND e.branch_id=@branch
                    AND e.deleted_at IS NULL)))";
    internal async Task<List<CommunicationCustomerRow>> CustomersAsync(string search)
    {
        int branch = RequireBranch();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(System.Data.IsolationLevel.RepeatableRead);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        await RequirePermissionAsync(db, tx, actor, branch, false);

        using var command = ScopedCommand(db, tx, branch, @"
            SELECT id,name,COALESCE(email,''),COALESCE(phone,''),active
            FROM public.communication_customer_recipients
            WHERE organization_id=@company AND branch_id=@branch
                AND (@search='' OR strpos(lower(concat_ws(' ',name,email,phone)),lower(@search))>0)
            ORDER BY lower(name),id LIMIT 250");
        command.Parameters.AddWithValue("search", search.Trim());
        using var reader = await command.ExecuteReaderAsync();
        var result = new List<CommunicationCustomerRow>();
        while (await reader.ReadAsync())
            result.Add(new(reader.GetInt32(0), reader.GetString(1), reader.GetString(2),
                reader.GetString(3), reader.GetBoolean(4)));
        return result;
    }

    internal async Task<CommunicationCustomerNotes> NotesAsync(int recipient)
    {
        int branch = RequireBranch();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(System.Data.IsolationLevel.RepeatableRead);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        await RequirePermissionAsync(db, tx, actor, branch, false);
        await VerifyRecipientAsync(db, tx, branch, recipient, false);

        var canAdd = false;
        if (actor.CanWriteBranch)
        {
            try
            {
                await RequirePermissionAsync(db, tx, actor, branch, true);
                canAdd = true;
            }
            catch (UnauthorizedAccessException) { }
        }
        using var command = ScopedCommand(db, tx, branch, @"
            SELECT note.body,COALESCE(author.email,''),note.created_at,COALESCE(assignee.email,''),
                note.follow_up_at,note.reminded_at IS NOT NULL
            FROM public.communication_customer_notes note
            LEFT JOIN public.users author ON author.id=note.created_by
            LEFT JOIN public.users assignee ON assignee.id=note.assigned_user_id
            WHERE note.organization_id=@company AND note.branch_id=@branch AND note.recipient_id=@recipient
            ORDER BY note.id DESC LIMIT 100");
        command.Parameters.AddWithValue("recipient", recipient);
        var rows = new List<CommunicationCustomerNote>();
        using (var reader = await command.ExecuteReaderAsync())
        {
            while (await reader.ReadAsync())
                rows.Add(new(reader.GetString(0), reader.GetString(1),
                    reader.IsDBNull(2) ? null : reader.GetDateTime(2).ToLocalTime(), reader.GetString(3),
                    reader.IsDBNull(4) ? null : reader.GetDateTime(4).ToLocalTime(), reader.GetBoolean(5)));
        }
        var assignees = new List<CommunicationNoteAssignee>();
        if (canAdd)
        {
            using var eligible = ScopedCommand(db, tx, branch, Eligible + " ORDER BY name,u.id");
            using var reader = await eligible.ExecuteReaderAsync();
            while (await reader.ReadAsync())
                assignees.Add(new(reader.GetInt32(0), reader.GetString(1)));
        }
        return new(rows, canAdd, assignees);
    }

    internal async Task AddNoteAsync(int recipient, string text, int? assignee = null, DateTimeOffset? followUp = null)
    {
        var body = text.Trim();
        if (body.Length == 0 || text.Length > 5000 || body.Contains('\0'))
            throw new ArgumentException("Enter a note between 1 and 5,000 characters.");
        int branch = RequireBranch();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        var actor = await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await RequirePermissionAsync(db, tx, actor, branch, true);
        await VerifyRecipientAsync(db, tx, branch, recipient, true);
        if (assignee is int id)
        {
            using var eligible = ScopedCommand(db, tx, branch, Eligible + " AND u.id=@assignee");
            eligible.Parameters.AddWithValue("assignee", id);
            if (await eligible.ExecuteScalarAsync() is null)
                throw new InvalidOperationException("Choose an assignee with access to this company and branch.");
        }

        using var command = ScopedCommand(db, tx, branch, @"
            INSERT INTO public.communication_customer_notes
                (organization_id,branch_id,recipient_id,body,created_by,assigned_user_id,follow_up_at)
            VALUES (@company,@branch,@recipient,@body,@actor,@assignee,@follow_up)");
        command.Parameters.AddWithValue("recipient", recipient);
        command.Parameters.AddWithValue("body", body);
        command.Parameters.AddWithValue("actor", actor.Id);
        command.Parameters.Add("assignee", NpgsqlDbType.Integer).Value = (object?)assignee ?? DBNull.Value;
        command.Parameters.Add("follow_up", NpgsqlDbType.TimestampTz).Value = (object?)followUp?.UtcDateTime ?? DBNull.Value;
        await command.ExecuteNonQueryAsync();
        await tx.CommitAsync();
    }

    internal async Task<List<CommunicationCustomerEmail>> EmailHistoryAsync(int recipient)
    {
        int branch = RequireBranch();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(System.Data.IsolationLevel.RepeatableRead);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        await RequirePermissionAsync(db, tx, actor, branch, false);
        await VerifyRecipientAsync(db, tx, branch, recipient, false);

        using var command = ScopedCommand(db, tx, branch, @"
            SELECT direction,subject,status,recorded,body FROM (
                SELECT 'Outbound' AS direction,d.subject,d.status,d.created_at AS recorded,d.body,d.id
                FROM public.communication_customer_deliveries d
                WHERE d.organization_id=@company AND d.branch_id=@branch
                    AND d.recipient_id=@recipient AND d.channel='email'
                UNION ALL
                SELECT 'Inbound',r.subject,'received',r.received_at,r.body,r.id
                FROM public.communication_customer_email_replies r
                JOIN public.communication_customer_deliveries d ON d.id=r.delivery_id
                    AND d.organization_id=r.organization_id AND d.branch_id=r.branch_id
                    AND d.recipient_id=r.recipient_id AND d.channel='email'
                WHERE r.organization_id=@company AND r.branch_id=@branch AND r.recipient_id=@recipient
            ) history ORDER BY recorded DESC NULLS LAST,direction,id DESC LIMIT 300");
        command.Parameters.AddWithValue("recipient", recipient);
        using var reader = await command.ExecuteReaderAsync();
        var rows = new List<CommunicationCustomerEmail>();
        while (await reader.ReadAsync())
            rows.Add(new(reader.GetString(0), reader.GetString(1), reader.GetString(2),
                reader.IsDBNull(3) ? null : reader.GetDateTime(3).ToLocalTime(), reader.GetString(4)));
        return rows;
    }

    internal async Task<int> ProcessOwnDueRemindersAsync()
    {
        int branch = RequireBranch();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        var actor = await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await RequirePermissionAsync(db, tx, actor, branch, true);

        using var command = ScopedCommand(db, tx, branch, $@"
            WITH eligible AS ({Eligible}),
            due AS (
                SELECT note.id FROM public.communication_customer_notes note
                JOIN public.communication_customer_recipients r ON r.id=note.recipient_id
                    AND r.organization_id=note.organization_id AND r.branch_id=note.branch_id
                WHERE note.organization_id=@company AND note.branch_id=@branch AND note.created_by=@actor
                    AND note.follow_up_at<=now() AND note.reminded_at IS NULL
                    AND (note.assigned_user_id IS NULL OR EXISTS (
                        SELECT 1 FROM eligible WHERE id=note.assigned_user_id))
                ORDER BY note.follow_up_at,note.id LIMIT 100 FOR UPDATE OF note SKIP LOCKED
            ), claimed AS (
                UPDATE public.communication_customer_notes note SET reminded_at=now()
                FROM due WHERE note.id=due.id AND note.reminded_at IS NULL
                RETURNING note.recipient_id,coalesce(note.assigned_user_id,note.created_by) AS recipient_user
            ), notices AS (
                INSERT INTO public.notifications (
                    company_id,user_id,title,message,module,event_type,related_entity_type,related_entity_id,
                    action_url,priority,channels,is_read)
                SELECT @company,recipient_user,'Customer follow-up due','A customer conversation needs your follow-up.',
                    'communication','customer.followup.due','customer_recipient',recipient_id,
                    '/crm/communication-hub?section=customers','normal','[""in_app""]'::json,false
                FROM claimed RETURNING id
            )
            INSERT INTO public.suite_branch_ownership(resource_table,resource_key,company_id,branch_id,source)
            SELECT 'notifications',id::text,@company,@branch,'validated-write' FROM notices");
        command.Parameters.AddWithValue("actor", actor.Id);
        int count = await command.ExecuteNonQueryAsync();
        await tx.CommitAsync();
        return count;
    }

    private const string OwnedReminder = @"n.company_id=@company AND n.user_id=@actor
        AND n.event_type='customer.followup.due' AND n.related_entity_type='customer_recipient'
        AND EXISTS (SELECT 1 FROM public.suite_branch_ownership b WHERE b.resource_table='notifications'
            AND b.resource_key=n.id::text AND b.company_id=@company AND b.branch_id=@branch)";

    internal async Task<List<CommunicationDeliveryRow>> ReminderHistoryAsync(string search, bool unreadOnly = false)
    {
        int branch = RequireBranch();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction(System.Data.IsolationLevel.RepeatableRead);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        await RequirePermissionAsync(db, tx, actor, branch, false);
        using var command = ScopedCommand(db, tx, branch, @"
            SELECT r.name,n.title,n.message,coalesce(n.is_read,false),n.created_at,n.id
            FROM public.notifications n
            JOIN public.communication_customer_recipients r
                ON r.id=n.related_entity_id AND r.organization_id=@company AND r.branch_id=@branch
            WHERE " + OwnedReminder + @"
                AND (NOT @unread_only OR NOT coalesce(n.is_read,false))
                AND (@search='' OR strpos(lower(concat_ws(' ',r.name,n.title)),lower(@search))>0)
            ORDER BY n.created_at DESC NULLS LAST,n.id DESC LIMIT 250");
        command.Parameters.AddWithValue("actor", actor.Id);
        command.Parameters.AddWithValue("search", search.Trim());
        command.Parameters.AddWithValue("unread_only", unreadOnly);
        using var reader = await command.ExecuteReaderAsync();
        var rows = new List<CommunicationDeliveryRow>();
        while (await reader.ReadAsync())
            rows.Add(new(reader.GetString(0), "In-app", "Customer follow-up", reader.GetBoolean(3) ? "Read" : "Unread",
                reader.IsDBNull(4) ? null : reader.GetDateTime(4).ToLocalTime(),
                reader.GetString(1) + Environment.NewLine + reader.GetString(2), reader.GetInt32(5)));
        return rows;
    }

    internal async Task<int> MarkRemindersReadAsync(int? notificationId)
    {
        int branch = RequireBranch();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        // Reading a personal notice does not require permission to edit the shared customer.
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        await RequirePermissionAsync(db, tx, actor, branch, false);
        using var command = ScopedCommand(db, tx, branch, @"
            UPDATE public.notifications n SET is_read=true, read_at=now()
            WHERE " + OwnedReminder + @"
                AND NOT coalesce(n.is_read,false) AND (@id IS NULL OR n.id=@id)
                AND EXISTS (SELECT 1 FROM public.communication_customer_recipients r
                    WHERE r.id=n.related_entity_id AND r.organization_id=@company AND r.branch_id=@branch)");
        command.Parameters.AddWithValue("actor", actor.Id);
        command.Parameters.Add("id", NpgsqlTypes.NpgsqlDbType.Integer).Value = (object?)notificationId ?? DBNull.Value;
        int updated = await command.ExecuteNonQueryAsync();
        await tx.CommitAsync();
        return updated;
    }

    private int RequireBranch() => settings.BranchId
        ?? throw new InvalidOperationException("Choose a branch to open customer communications.");

    private async Task RequirePermissionAsync(NpgsqlConnection db, NpgsqlTransaction tx, DesktopActor actor,
        int branch, bool write)
    {
        var grant = await DesktopModuleAccess.RequireAsync(db, tx, settings.OrganizationId, branch, actor,
            "communication", write ? "create" : "view", write ? "communication_email_send" : "communication_view");
        if (grant.Scope is not ("organization" or "branch"))
            throw new UnauthorizedAccessException("Customer communications require branch-wide or organization-wide access.");
    }

    private async Task VerifyRecipientAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch,
        int recipient, bool write)
    {
        const string statement = @"SELECT id FROM public.communication_customer_recipients
            WHERE organization_id=@company AND branch_id=@branch AND id=@recipient";
        using var command = ScopedCommand(db, tx, branch, write ? statement + " FOR SHARE" : statement);
        command.Parameters.AddWithValue("recipient", recipient);
        if (await command.ExecuteScalarAsync() is null)
            throw new InvalidOperationException("The recipient is unavailable in the selected branch.");
    }

    private NpgsqlCommand ScopedCommand(NpgsqlConnection db, NpgsqlTransaction tx, int branch, string sql)
    {
        var command = new NpgsqlCommand(sql, db, tx);
        command.Parameters.AddWithValue("company", settings.OrganizationId);
        command.Parameters.AddWithValue("branch", branch);
        return command;
    }
}
