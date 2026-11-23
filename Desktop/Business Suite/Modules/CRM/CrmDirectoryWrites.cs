using System.Net.Mail;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record CrmRecordKey(int Id, string Revision, int? DetailsRevision);
internal sealed record CrmRecordDraft(string Name, string LastName, string Detail, string Industry, string Email,
    string Phone, string PhoneCode, string Website, string Address, string City, string State, string Country,
    string Status, string Classification, string Tags, string Notes, int? CompanyId, int? BranchId = null);
internal sealed record CrmLookup(int? Id, string Name);
internal sealed class CrmDuplicateException(string message) : InvalidOperationException(message);

internal static class CrmDirectoryWrites
{
    internal static readonly string[] CompanyRoles = ["Lead", "Prospect", "Customer", "Vendor", "Supplier", "Partner",
        "Friend", "Consultant", "Dealer", "Distributor", "Investor", "Other"];
    internal static readonly string[] ContactStages = ["Lead", "Prospect", "Opportunity", "Customer", "Inactive"];

    internal static async Task<DesktopActor> RequireCrmActorAsync(DesktopDatabaseSettings settings,
        NpgsqlConnection db, NpgsqlTransaction tx, CancellationToken cancellation, string entity, string action = "view")
    {
        var actor = await settings.RequireActorAsync(db, tx, cancellation);
        await RequireCrmAccessAsync(settings, db, tx, actor, entity, action);
        return actor;
    }

    internal static async Task RequireCrmAccessAsync(DesktopDatabaseSettings settings, NpgsqlConnection db,
        NpgsqlTransaction tx, DesktopActor actor, string entity, string action)
    {
        RequireCrmAccess(actor);
        string manage = $"crm_{entity}_manage";
        string[] permissions = action == "view"
            ? ["crm_view", "crm_manage", "crm_admin", $"crm_{entity}_view", manage]
            : ["crm_manage", "crm_admin", manage];
        var grant = await DesktopModuleAccess.RequireAsync(db, tx, settings.OrganizationId, settings.BranchId ?? 0,
            actor, "crm", action, permissions);
        if (grant.Scope is not ("organization" or "branch") || (grant.Scope == "branch" && !settings.BranchId.HasValue))
            throw new UnauthorizedAccessException("This CRM workflow requires branch-wide or organization-wide access.");
    }

    internal static void RequireCrmAccess(DesktopActor actor)
    {
        if (!actor.IsSuperuser && !actor.IsCompanyAdmin)
            throw new UnauthorizedAccessException("This desktop CRM workflow requires a Suite company administrator.");
    }

    internal static string PermissionEntity(CrmDirectoryKind kind) =>
        kind == CrmDirectoryKind.Companies ? "accounts" : "contacts";

    // Table and alias come from the fixed CRM record types used by the caller.
    internal static string BranchScope(string table, string alias, bool includeShares = false)
    {
        string shares = includeShares ? $@" OR EXISTS (
            SELECT 1 FROM public.suite_branch_record_shares share
            WHERE share.company_id={alias}.organization_id AND share.resource_table='{table}'
              AND share.resource_key={alias}.id::text AND share.branch_id=@scope_branch)" : "";
        return $@"(@scope_branch IS NULL OR COALESCE((
            SELECT ownership.branch_id FROM public.suite_branch_ownership ownership
            WHERE ownership.company_id={alias}.organization_id AND ownership.resource_table='{table}'
              AND ownership.resource_key={alias}.id::text), {alias}.branch_id)=@scope_branch{shares})"
            +(table is "crm_companies" or "crm_contacts"?" AND "+PublicPartyScope(table,alias):"");
    }

    internal static string PublicPartyScope(string table,string alias)
    {
        string linked=table switch
        {
            "crm_companies"=>$"cash.customer_id={alias}.id",
            "crm_contacts"=>$@"(cash.customer_id={alias}.company_id OR EXISTS (
                SELECT 1 FROM public.suite_contact_identity_links identity
                WHERE identity.organization_id={alias}.organization_id AND identity.contact_id={alias}.id
                    AND identity.account_id=cash.customer_id))",
            _=>throw new ArgumentException("Only CRM companies and contacts are master party records.")
        };
        return $@"NOT EXISTS (SELECT 1 FROM public.srm_anonymous_cash_accounts cash
            WHERE cash.organization_id={alias}.organization_id AND {linked})";
    }

    internal static async Task CheckReservedCompanyNameAsync(NpgsqlConnection db,NpgsqlTransaction tx,int org,string name,
        CancellationToken cancellation)
    {
        using var command=Command(db,tx,@"SELECT 1 FROM public.srm_anonymous_cash_accounts cash
            JOIN public.crm_companies c ON c.id=cash.customer_id AND c.organization_id=cash.organization_id
            WHERE cash.organization_id=@org AND lower(trim(c.name))=lower(trim(@name)) LIMIT 1",org,null);
        AddText(command,"name",name);
        if (await command.ExecuteScalarAsync(cancellation) is not null)
            throw new InvalidOperationException("This company name is unavailable. Choose another name.");
    }

    public static async Task<int> SaveAsync(CrmDirectoryKind kind, CrmRecordKey? key, CrmRecordDraft draft,
        CancellationToken cancellation, string? duplicateReason = null, CrmExtras? extras = null)
    {
        bool company = kind == CrmDirectoryKind.Companies;
        CrmExtras? original = extras is null ? null : CrmExtrasStore.Decode(extras.Snapshot, extras.Snapshot);
        if (extras is not null && original is not null)
        {
            if (extras.Gst != original.Gst || System.Text.Json.JsonSerializer.Serialize(extras.Tax, CrmExtrasStore.Json)
                != System.Text.Json.JsonSerializer.Serialize(original.Tax, CrmExtrasStore.Json))
                CrmExtrasStore.ValidateTax(extras, company);
            if (extras.ChannelsEdited)
            {
                CrmExtrasStore.NormalizeChannels(extras.Channels);
                CrmChannel? phone = extras.Channels.FirstOrDefault(item => item.Kind == "phone" && item.Primary);
                string email = extras.Channels.FirstOrDefault(item => item.Kind == "email" && item.Primary)?.Value ?? "";
                if (email.Length > 150)
                    throw new ArgumentException("The primary email must be 150 characters or fewer.");
                draft = draft with { Email = email, Phone = phone?.Value ?? "", PhoneCode = phone?.CountryCode ?? "" };
            }
        }
        CrmPhoneNumber? normalizedPhone = draft.Phone.Length == 0 ? null : CrmPhone.Normalize(draft.Phone, draft.PhoneCode);
        if (normalizedPhone is not null)
            draft = draft with { Phone = normalizedPhone.National, PhoneCode = normalizedPhone.CallingCode };
        string[] roles = draft.Classification.Split(',').Select(value => value.Trim())
            .Where(value => value.Length > 0).Distinct(StringComparer.Ordinal).ToArray();
        Validate(company, draft, roles);
        var settings = DesktopDatabaseSettings.Load();
        using var connection = new NpgsqlConnection(settings.ConnectionString);
        await connection.OpenAsync(cancellation);
        using var transaction = connection.BeginTransaction(System.Data.IsolationLevel.Serializable);
        var actor = await settings.VerifyWriteTargetAsync(connection, transaction, cancellation);
        await RequireCrmAccessAsync(settings, connection, transaction, actor, PermissionEntity(kind), key is null ? "create" : "edit");
        if (!company && draft.CompanyId.HasValue)
            await RequireCrmAccessAsync(settings, connection, transaction, actor, "accounts", "view");
        string table = Table(kind);

        string[] locks = [
            company ? "company-name:" + draft.Name.ToLowerInvariant() : "",
            draft.Email.ToLowerInvariant(),
            normalizedPhone?.International ?? ""
        ];
        var extraLocks = extras is null ? Array.Empty<string>() : extras.Tax.Select(item => "tax:" + item.Number)
            .Concat(extras.ChannelsEdited ? extras.Channels.Select(item => item.Normalized!) : Array.Empty<string>());
        await LockDuplicates(connection, transaction, settings.OrganizationId, locks.Concat(extraLocks), cancellation);
        if (company)
            await CheckReservedCompanyNameAsync(connection,transaction,settings.OrganizationId,draft.Name,cancellation);
        if (key is not null)
        {
            await CheckCurrent(connection, transaction, table, settings, key, false, cancellation);
            if (company)
            {
                using var existing = Command(connection, transaction, @"SELECT role FROM public.suite_business_relationships
                    WHERE organization_id=@org AND account_id=@id
                    UNION
                    SELECT account_type FROM public.crm_companies WHERE organization_id=@org AND id=@id AND account_type IS NOT NULL
                      AND NOT EXISTS (SELECT 1 FROM public.suite_business_relationships WHERE organization_id=@org AND account_id=@id)",
                    settings.OrganizationId, key.Id);
                var preserved = new HashSet<string>(roles, StringComparer.Ordinal);
                using var reader = await existing.ExecuteReaderAsync(cancellation);
                while (await reader.ReadAsync(cancellation))
                    if (CompanyRoles.Contains(reader.GetString(0)))
                        preserved.Add(reader.GetString(0));
                roles = preserved.ToArray();
            }
        }
        if (extras is not null && extras.Snapshot != await CrmExtrasStore.ReadSnapshot(connection, transaction,
                settings.OrganizationId, kind, key?.Id, cancellation))
            throw new InvalidOperationException("Custom fields, tax details, or channels changed. Reopen the editor.");

        string? duplicate = await FindDuplicate(connection, transaction, table, settings.OrganizationId,
            key?.Id, draft, company, normalizedPhone?.International, cancellation);
        bool hasDuplicate = duplicate is not null;
        if (extras is not null && original is not null && !hasDuplicate)
            hasDuplicate = await CrmExtrasWrites.HasDuplicateAsync(connection, transaction, settings.OrganizationId,
                kind, key?.Id, extras, original, cancellation);
        if (hasDuplicate && (duplicateReason?.Trim().Length ?? 0) < 5)
            throw new CrmDuplicateException("A matching record, channel or tax number already exists. Review it or enter a reason to save separately.");
        string? linkedName = !company && draft.CompanyId is int companyId
            ? await CheckLinkedCompany(connection, transaction, settings, companyId, cancellation)
            : null;

        int? branch = key is null ? await CreationBranch(connection, transaction, settings, draft.BranchId, cancellation) : null;
        string statement = (company, key is null) switch
        {
            (true, true) => @"INSERT INTO public.crm_companies
                (organization_id, branch_id, name, industry, email, phone, phone_country_code,
                 website, address, city, state, country, status, account_type, tags_text, notes, updated_at)
                VALUES (@org, @branch, @name, @industry, @email, @phone, @phone_code,
                 @website, @address, @city, @state, @country, @status, @category, @tags, @notes, now())
                RETURNING id",
            (true, false) => @"UPDATE public.crm_companies SET
                name=@name, industry=@industry, email=@email, phone=@phone, phone_country_code=@phone_code,
                website=@website, address=@address, city=@city, state=@state, country=@country,
                status=@status, account_type=@category, tags_text=@tags, notes=@notes, updated_at=now()
                WHERE organization_id=@org AND id=@id RETURNING id",
            (false, true) => @"INSERT INTO public.crm_contacts
                (organization_id, branch_id, first_name, last_name, full_name, job_title, company_id, company_name,
                 email, phone, phone_country_code, website, address, city, state, country, status,
                 lifecycle_stage, tags_text, notes, updated_at)
                VALUES (@org, @branch, @name, @last_name, @full_name, @detail, @company_id, @company_name,
                 @email, @phone, @phone_code, @website, @address, @city, @state, @country, @status,
                 @category, @tags, @notes, now()) RETURNING id",
            _ => @"UPDATE public.crm_contacts SET
                first_name=@name, last_name=@last_name, full_name=@full_name, job_title=@detail, company_id=@company_id,
                company_name=CASE WHEN @company_id IS NULL AND company_id IS NULL THEN company_name ELSE @company_name END,
                email=@email, phone=@phone, phone_country_code=@phone_code, website=@website,
                address=@address, city=@city, state=@state, country=@country, status=@status,
                lifecycle_stage=@category, tags_text=@tags, notes=@notes, updated_at=now()
                WHERE organization_id=@org AND id=@id RETURNING id"
        };
        using var write = Command(connection, transaction, statement, settings.OrganizationId, key?.Id);
        Add(write, "branch", NpgsqlDbType.Integer, branch);
        Add(write, "company_id", NpgsqlDbType.Integer, draft.CompanyId);
        Add(write, "company_name", NpgsqlDbType.Text, linkedName);
        AddText(write, "name", draft.Name);
        AddText(write, "last_name", draft.LastName);
        AddText(write, "full_name", (draft.Name + " " + draft.LastName).Trim());
        AddText(write, "detail", draft.Detail);
        AddText(write, "industry", draft.Industry);
        AddText(write, "email", draft.Email);
        AddText(write, "phone", draft.Phone);
        AddText(write, "phone_code", draft.Phone.Length == 0 ? "" : draft.PhoneCode);
        AddText(write, "website", draft.Website);
        AddText(write, "address", draft.Address);
        AddText(write, "city", draft.City);
        AddText(write, "state", draft.State);
        AddText(write, "country", draft.Country);
        AddText(write, "status", draft.Status);
        AddText(write, "category", company ? PrimaryRole(roles) : draft.Classification);
        AddText(write, "tags", draft.Tags);
        AddText(write, "notes", draft.Notes);
        int id = (int)(await write.ExecuteScalarAsync(cancellation))!;

        if (company)
            await SaveCompanyDetails(connection, transaction, settings.OrganizationId, id, key?.DetailsRevision,
                draft.Detail, roles, cancellation);
        if (extras is not null && original is not null)
            await CrmExtrasWrites.SaveAsync(connection, transaction, settings.OrganizationId, id, kind, extras, original, cancellation);
        if (normalizedPhone is not null && extras?.ChannelsEdited != true)
            await CrmExtrasWrites.EnsurePrimaryPhoneAsync(connection, transaction, settings.OrganizationId,
                id, company, normalizedPhone, cancellation);
        await CheckRequiredFieldsAsync(connection, transaction, company ? "companies" : "contacts", settings.OrganizationId, id, cancellation);
        if (branch.HasValue)
        {
            using var ownership = Command(connection, transaction, @"INSERT INTO public.suite_branch_ownership
                (resource_table, resource_key, company_id, branch_id, source)
                VALUES (@table, @id::text, @org, @branch, 'desktop-crm')", settings.OrganizationId, id);
            AddText(ownership, "table", table);
            Add(ownership, "branch", NpgsqlDbType.Integer, branch);
            await ownership.ExecuteNonQueryAsync(cancellation);
        }

        await Audit(connection, transaction, table, settings.OrganizationId, id, actor.Id, key is null ? "CREATE" : "UPDATE", cancellation);
        if (hasDuplicate)
            await Audit(connection, transaction, table, settings.OrganizationId, id, actor.Id, "SHARED_CONTACT_CONFIRMED",
                cancellation, duplicateReason);
        transaction.Commit();
        return id;
    }

    internal static async Task<(List<CrmLookup> Branches, List<CrmLookup> Companies, int? DefaultBranch)>
        ReadEditorChoicesAsync(string entity, bool creating, CancellationToken cancellation)
    {
        var settings = DesktopDatabaseSettings.Load();
        using var connection = new NpgsqlConnection(settings.ConnectionString);
        await connection.OpenAsync(cancellation);
        using var tx = connection.BeginTransaction(System.Data.IsolationLevel.RepeatableRead);
        var actor = await RequireCrmActorAsync(settings, connection, tx, cancellation, entity, creating ? "create" : "edit");
        var branches = new List<CrmLookup>();
        var companies = new List<CrmLookup> { new(null, "No linked company") };
        if (creating)
            await ReadAsync(@"SELECT b.id, b.name FROM public.branches b WHERE b.company_id=@org AND b.is_active AND (@scope_branch IS NULL OR b.id=@scope_branch)
                AND NOT EXISTS (SELECT 1 FROM public.suite_branch_lifecycle l WHERE l.branch_id=b.id AND l.deleted_at IS NOT NULL)
                ORDER BY b.name, b.id", branches);
        if (entity == "contacts")
        {
            await RequireCrmAccessAsync(settings, connection, tx, actor, "accounts", "view");
            await ReadAsync("SELECT id, name FROM public.crm_companies c WHERE organization_id=@org " +
                "AND deleted_at IS NULL AND " + BranchScope("crm_companies", "c", includeShares: true) +
                " ORDER BY name, id", companies);
        }
        return (branches, companies, settings.BranchId);

        async Task ReadAsync(string sql, List<CrmLookup> output)
        {
            using var command = new NpgsqlCommand(sql, connection, tx);
            Add(command, "org", NpgsqlDbType.Integer, settings.OrganizationId);
            Add(command, "scope_branch", NpgsqlDbType.Integer, settings.BranchId);
            using var reader = await command.ExecuteReaderAsync(cancellation);
            while (await reader.ReadAsync(cancellation))
                output.Add(new(reader.GetInt32(0), reader.GetString(1)));
        }
    }

    public static async Task ChangeArchiveAsync(CrmDirectoryKind kind, CrmRecordKey key, bool archive,
        CancellationToken cancellation)
    {
        var settings = DesktopDatabaseSettings.Load();
        using var connection = new NpgsqlConnection(settings.ConnectionString);
        await connection.OpenAsync(cancellation);
        using var transaction = connection.BeginTransaction();
        var actor = await settings.VerifyWriteTargetAsync(connection, transaction, cancellation);
        await RequireCrmAccessAsync(settings, connection, transaction, actor, PermissionEntity(kind), "delete");
        string table = Table(kind);
        await CheckCurrent(connection, transaction, table, settings, key, !archive, cancellation);
        if (!archive)
        {
            using var merged = Command(connection, transaction, @"SELECT EXISTS (
                SELECT 1 FROM public.crm_activities
                WHERE organization_id=@org AND entity_type=@entity AND entity_id=@id
                  AND activity_type='duplicate_merge' AND metadata_json->>'loserId'=@id::text)",
                settings.OrganizationId, key.Id);
            AddText(merged, "entity", kind == CrmDirectoryKind.Companies ? "account" : "contact");
            if ((bool)(await merged.ExecuteScalarAsync(cancellation))!)
                throw new InvalidOperationException("This record was merged. Open the surviving record.");
            if (kind == CrmDirectoryKind.Contacts)
            {
                using var linked = Command(connection, transaction,
                    "SELECT company_id FROM public.crm_contacts WHERE organization_id=@org AND id=@id",
                    settings.OrganizationId, key.Id);
                if (await linked.ExecuteScalarAsync(cancellation) is int companyId)
                    await CheckLinkedCompany(connection, transaction, settings, companyId, cancellation);
            }
            else
            {
                using var linked = Command(connection, transaction,
                    "SELECT parent_company_id FROM public.crm_companies WHERE organization_id=@org AND id=@id",
                    settings.OrganizationId, key.Id);
                if (await linked.ExecuteScalarAsync(cancellation) is int parentId && parentId != key.Id)
                    await CheckLinkedCompany(connection, transaction, settings, parentId, cancellation);
            }
        }

        using var write = Command(connection, transaction,
            $"UPDATE public.{table} SET deleted_at=CASE WHEN @archive THEN now() ELSE NULL END, updated_at=now() " +
            "WHERE organization_id=@org AND id=@id", settings.OrganizationId, key.Id);
        Add(write, "archive", NpgsqlDbType.Boolean, archive);
        await write.ExecuteNonQueryAsync(cancellation);
        await Audit(connection, transaction, table, settings.OrganizationId, key.Id, actor.Id, archive ? "DELETE" : "RESTORE", cancellation);
        transaction.Commit();
    }

    private static async Task CheckCurrent(NpgsqlConnection db, NpgsqlTransaction tx, string table, DesktopDatabaseSettings settings,
        CrmRecordKey key, bool archived, CancellationToken cancellation)
    {
        using var command = Command(db, tx, $"SELECT xmin::text FROM public.{table} r WHERE organization_id=@org " +
            "AND id=@id AND (deleted_at IS NOT NULL)=@archived AND " + BranchScope(table, "r") +
            " FOR UPDATE", settings.OrganizationId, key.Id);
        Add(command, "scope_branch", NpgsqlDbType.Integer, settings.BranchId);
        Add(command, "archived", NpgsqlDbType.Boolean, archived);
        if ((string?)await command.ExecuteScalarAsync(cancellation) != key.Revision)
            throw new InvalidOperationException("This record changed. Refresh the directory before trying again.");
    }

    private static async Task<string> CheckLinkedCompany(NpgsqlConnection db, NpgsqlTransaction tx, DesktopDatabaseSettings settings,
        int id, CancellationToken cancellation)
    {
        using var command = Command(db, tx, "SELECT name FROM public.crm_companies c WHERE organization_id=@org " +
            "AND id=@id AND deleted_at IS NULL AND " + BranchScope("crm_companies", "c", includeShares: true) +
            " FOR SHARE", settings.OrganizationId, id);
        Add(command, "scope_branch", NpgsqlDbType.Integer, settings.BranchId);
        if (await command.ExecuteScalarAsync(cancellation) is not string name)
            throw new InvalidOperationException("Choose an active company in this organization. Restore the linked company first if needed.");
        return name;
    }

    internal static async Task<int> CreationBranch(NpgsqlConnection db, NpgsqlTransaction tx,
        DesktopDatabaseSettings settings, int? selectedBranch, CancellationToken cancellation)
    {
        if (selectedBranch.HasValue && settings.BranchId.HasValue && selectedBranch != settings.BranchId)
            throw new InvalidOperationException("Choose the configured branch.");
        using var command = Command(db, tx, @"SELECT b.id FROM public.branches b
            WHERE b.company_id=@org AND b.is_active AND (@branch IS NULL OR b.id=@branch)
              AND NOT EXISTS (SELECT 1 FROM public.suite_branch_lifecycle l WHERE l.branch_id=b.id AND l.deleted_at IS NOT NULL)
            ORDER BY b.id LIMIT 2 FOR SHARE", settings.OrganizationId);
        Add(command, "branch", NpgsqlDbType.Integer, selectedBranch ?? settings.BranchId);
        using var reader = await command.ExecuteReaderAsync(cancellation);
        if (!await reader.ReadAsync(cancellation))
            throw new InvalidOperationException("Create or restore an active branch before adding CRM records.");
        int branch = reader.GetInt32(0);
        if (await reader.ReadAsync(cancellation))
            throw new InvalidOperationException("Choose the branch for this record.");
        return branch;
    }

    private static async Task LockDuplicates(NpgsqlConnection db, NpgsqlTransaction tx, int organization,
        IEnumerable<string> keys, CancellationToken cancellation)
    {
        using var hash = System.Security.Cryptography.SHA256.Create();
        using var command = new NpgsqlCommand("SELECT pg_advisory_xact_lock(@token)", db, tx);
        var parameter = command.Parameters.Add("token", NpgsqlDbType.Bigint);
        foreach (string key in keys.Where(value => value.Length != 0).Distinct().OrderBy(value => value, StringComparer.Ordinal))
        {
            byte[] digest = hash.ComputeHash(System.Text.Encoding.UTF8.GetBytes($"contacts:{organization}:{key}"));
            long token = digest.Take(8).Aggregate(0L, (value, next) => unchecked((value << 8) | next));
            parameter.Value = token & long.MaxValue;
            await command.ExecuteNonQueryAsync(cancellation);
        }
    }

    private static async Task<string?> FindDuplicate(NpgsqlConnection db, NpgsqlTransaction tx, string table, int org,
        int? id, CrmRecordDraft draft, bool company, string? internationalPhone, CancellationToken cancellation)
    {
        using var command = Command(db, tx, $@"WITH current_record AS (
                SELECT lower(trim(email)) AS email,
                       CASE WHEN trim(phone) LIKE '+%' THEN regexp_replace(phone,'[ ().-]','','g')
                            WHEN phone_country_code IS NOT NULL THEN phone_country_code || regexp_replace(phone,'[ ().-]','','g')
                       END AS phone
                FROM public.{table} WHERE organization_id=@org AND id=@id
            ), candidates AS (
                SELECT id, 'crm_companies' AS kind, name, email, phone_country_code, phone FROM public.crm_companies candidate
                  WHERE organization_id=@org AND deleted_at IS NULL AND {PublicPartyScope("crm_companies","candidate")}
                UNION ALL
                SELECT id, 'crm_contacts', full_name, email, phone_country_code, phone FROM public.crm_contacts candidate
                  WHERE organization_id=@org AND deleted_at IS NULL AND {PublicPartyScope("crm_contacts","candidate")}
            )
            SELECT (CASE WHEN kind='crm_companies' THEN 'Company #' ELSE 'Contact #' END) || id::text || ' – ' || left(name, 100)
            FROM candidates
            WHERE NOT (kind=@kind AND id IS NOT DISTINCT FROM @id)
              AND NOT EXISTS (
                SELECT 1 FROM public.suite_contact_identity_links link WHERE link.organization_id=@org AND (
                    (@kind='crm_companies' AND candidates.kind='crm_contacts' AND link.account_id=@id AND link.contact_id=candidates.id)
                    OR (@kind='crm_contacts' AND candidates.kind='crm_companies' AND link.contact_id=@id AND link.account_id=candidates.id)))
              AND (
                (@check_name AND kind='crm_companies' AND lower(trim(name))=lower(@name))
                OR (@email IS NOT NULL AND lower(@email) IS DISTINCT FROM (SELECT email FROM current_record)
                    AND lower(trim(email))=lower(@email))
                OR (@phone IS NOT NULL AND @phone IS DISTINCT FROM (SELECT phone FROM current_record)
                    AND ((CASE WHEN trim(candidates.phone) LIKE '+%' THEN regexp_replace(candidates.phone,'[ ().-]','','g')
                         WHEN candidates.phone_country_code IS NOT NULL THEN candidates.phone_country_code || regexp_replace(candidates.phone,'[ ().-]','','g')
                    END)=@phone OR EXISTS (
                        SELECT 1 FROM public.suite_contact_channels channel
                        WHERE channel.organization_id=@org AND channel.kind='phone' AND channel.normalized_value=@phone
                          AND ((candidates.kind='crm_companies' AND channel.account_id=candidates.id)
                            OR (candidates.kind='crm_contacts' AND channel.contact_id=candidates.id)))))
            ) ORDER BY kind, id LIMIT 1", org, id);
        AddText(command, "kind", table);
        AddText(command, "name", draft.Name);
        AddText(command, "email", draft.Email);
        Add(command, "phone", NpgsqlDbType.Text, internationalPhone);
        Add(command, "check_name", NpgsqlDbType.Boolean, company && id is null);
        return (string?)await command.ExecuteScalarAsync(cancellation);
    }

    internal static async Task CheckRequiredFieldsAsync(NpgsqlConnection db, NpgsqlTransaction tx, string entity, int org,
        int? id, CancellationToken cancellation)
    {
        using var command = Command(db, tx, @"SELECT f.label FROM public.crm_custom_fields f
            WHERE f.organization_id=@org AND f.entity=@entity AND f.is_active AND f.is_required AND f.deleted_at IS NULL
              AND NOT EXISTS (SELECT 1 FROM public.crm_custom_field_values v
                WHERE v.organization_id=@org AND v.entity=f.entity AND v.custom_field_id=f.id AND v.record_id=@id
                  AND v.deleted_at IS NULL AND (NULLIF(trim(v.value_text),'') IS NOT NULL OR v.value_number IS NOT NULL
                    OR v.value_boolean IS NOT NULL OR v.value_date IS NOT NULL OR v.value_datetime IS NOT NULL
                    OR (v.value_json IS NOT NULL AND v.value_json::text NOT IN ('null','[]','{}'))))
            ORDER BY f.position, f.id LIMIT 1", org, id);
        AddText(command, "entity", entity);
        if (await command.ExecuteScalarAsync(cancellation) is string label)
            throw new InvalidOperationException($"Enter a value for the required custom field {label}.");
    }

    private static async Task SaveCompanyDetails(NpgsqlConnection db, NpgsqlTransaction tx, int org, int id,
        int? expectedVersion, string legalName, string[] roles, CancellationToken cancellation)
    {
        using var details = Command(db, tx, expectedVersion.HasValue
            ? @"UPDATE public.suite_company_master_details SET legal_name=@name, version=version+1
                WHERE organization_id=@org AND account_id=@id AND version=@version"
            : @"INSERT INTO public.suite_company_master_details
                (organization_id, account_id, legal_name, addresses, tax_registrations, version)
                VALUES (@org, @id, @name, '[]'::json, '[]'::json, 1) ON CONFLICT (account_id) DO NOTHING", org, id);
        AddText(details, "name", legalName);
        Add(details, "version", NpgsqlDbType.Integer, expectedVersion);
        if (await details.ExecuteNonQueryAsync(cancellation) != 1)
            throw new InvalidOperationException("The company profile changed. Refresh the directory before saving.");

        using var add = Command(db, tx, @"INSERT INTO public.suite_business_relationships
            (organization_id, account_id, role, status)
            SELECT @org, @id, role, 'Active' FROM unnest(@roles) AS role
            ON CONFLICT (account_id, role) DO NOTHING", org, id);
        Add(add, "roles", NpgsqlDbType.Array | NpgsqlDbType.Text, roles);
        await add.ExecuteNonQueryAsync(cancellation);
    }

    internal static async Task Audit(NpgsqlConnection db, NpgsqlTransaction tx, string table, int org, int id,
        int actorId, string action, CancellationToken cancellation, string? reason = null)
    {
        using var command = Command(db, tx, @"INSERT INTO public.audit_logs
            (organization_id, user_id, actor_authenticated, method, entity_type, entity_id, action, description, module)
            VALUES (@org, @actor, TRUE, 'CRM', @table, @id, @action, @description, 'crm')", org, id);
        Add(command, "actor", NpgsqlDbType.Integer, actorId);
        AddText(command, "table", table);
        AddText(command, "action", action);
        AddText(command, "description", reason is null ? "Business Suite Desktop" : $"Business Suite Desktop · {reason}");
        await command.ExecuteNonQueryAsync(cancellation);
    }

    private static void Validate(bool company, CrmRecordDraft draft, string[] roles)
    {
        if (draft.Name.Length == 0 || draft.Name.Length > (company ? 180 : 100))
            throw new ArgumentException(company ? "Enter a company name of up to 180 characters." : "Enter a first name of up to 100 characters.");
        if (!new[] { "Active", "Inactive", "Blocked" }.Contains(draft.Status))
            throw new ArgumentException("Choose Active, Inactive, or Blocked.");
        if (company && (roles.Length == 0 || roles.Any(role => !CompanyRoles.Contains(role))))
            throw new ArgumentException("Choose at least one business relationship.");
        if (!company && !ContactStages.Contains(draft.Classification))
            throw new ArgumentException("Choose Lead, Prospect, Opportunity, Customer, or Inactive.");
        if (draft.Email.Length > 0)
        {
            try
            {
                if (!string.Equals(new MailAddress(draft.Email).Address, draft.Email, StringComparison.OrdinalIgnoreCase))
                    throw new FormatException();
            }
            catch (FormatException) { throw new ArgumentException("Enter a valid email address."); }
        }
        if (draft.Website.Length > 0 && (!Uri.TryCreate(draft.Website, UriKind.Absolute, out Uri? url)
                || !(url.Scheme == "http" || url.Scheme == "https") || url.UserInfo.Length != 0 || url.Host.Length == 0))
            throw new ArgumentException("Enter a website that starts with http:// or https://.");
    }

    private static string PrimaryRole(string[] roles) =>
        new[] { "Customer", "Vendor", "Supplier", "Partner", "Prospect" }.FirstOrDefault(roles.Contains) ?? "Other";

    private static string Table(CrmDirectoryKind kind) =>
        kind == CrmDirectoryKind.Companies ? "crm_companies" : "crm_contacts";

    private static NpgsqlCommand Command(NpgsqlConnection db, NpgsqlTransaction transaction, string sql, int organization, int? id = null)
    {
        var command = new NpgsqlCommand(sql, db, transaction);
        Add(command, "org", NpgsqlDbType.Integer, organization);
        Add(command, "id", NpgsqlDbType.Integer, id);
        return command;
    }

    private static void AddText(NpgsqlCommand command, string name, string value) =>
        Add(command, name, NpgsqlDbType.Text, value.Length == 0 ? null : value);

    private static void Add(NpgsqlCommand command, string name, NpgsqlDbType type, object? value) =>
        command.Parameters.Add(name, type).Value = value ?? DBNull.Value;
}
