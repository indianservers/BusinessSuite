using System.Security.Cryptography;
using System.Text;
using Npgsql;

namespace Business_Suite;

internal sealed partial class SalesOrderRepository
{
    internal Task<PosAnonymousConfiguration> CreatePosAnonymousConfigurationAsync(
        string label, string country, bool enabled, string reason) =>
        ProvisionPosAnonymousConfigurationAsync(label, country, enabled, reason, null);

    internal Task<PosAnonymousConfiguration> SelectPosAnonymousConfigurationAsync(
        string label, string country, bool enabled, string reason, int customer)
    {
        if (customer < 1)
            throw new ArgumentException("Enter the positive ID of the existing dedicated account.");
        return ProvisionPosAnonymousConfigurationAsync(label, country, enabled, reason, customer);
    }

    private async Task<PosAnonymousConfiguration> ProvisionPosAnonymousConfigurationAsync(
        string label, string country, bool enabled, string reason, int? customer)
    {
        label = label.Trim();
        country = country.Trim().ToUpperInvariant();
        reason = reason.Trim();
        if (label.Length is < 1 or > 180 || label.Any(char.IsControl) || !AnonymousJurisdictions.Value.ContainsKey(country))
            throw new ArgumentException("Enter a ledger label and a supported two-letter jurisdiction.");
        if (reason.Length is < 8 or > 1000)
            throw new ArgumentException("Enter a reason of 8 to 1,000 characters.");

        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose a branch to provision a counter account.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        if ((!actor.IsSuperuser && !actor.IsCompanyAdmin) || !actor.CanWriteBranch)
            throw new UnauthorizedAccessException("A company administrator with branch write access is required.");
        await RequireRegisterWriterAsync(db, tx, branch, actor);
        await RequireNativeRegisterBranchAsync(db, tx, branch, "counter account provisioning");
        var current = await ReadPosAnonymousConfigurationAsync(db, tx, branch, actor.Id, true);
        if (current is not null)
        {
            if (current.Label != label || current.Country != country || current.Enabled != enabled ||
                (customer.HasValue && current.CustomerId != customer.Value))
                throw new InvalidOperationException("This branch already has a counter account. Its ledger identity is permanent.");
            tx.Commit();
            return current;
        }

        if (customer is int dedicated)
        {
            await SelectExistingPosAnonymousAsync(db, tx, branch, actor.Id, dedicated, label, country, enabled, reason);
        }
        else
        {
            await InsertNewPosAnonymousAsync(db, tx, branch, actor.Id, label, country, enabled, reason);
        }
        if (await ResolveAnonymousCheckoutBuyerAsync(db, tx, branch, actor.Id, lockRows: true, requireActive: false) is null ||
            await ReadPosAnonymousConfigurationAsync(db, tx, branch, actor.Id, false) is not { } saved)
            throw new InvalidOperationException("The dedicated counter account does not have a verified private ledger identity.");
        tx.Commit();
        return saved;
    }

    private async Task InsertNewPosAnonymousAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, int actor,
        string label, string country, bool enabled, string reason)
    {
        using (var hash = SHA256.Create())
        {
            byte[] digest = hash.ComputeHash(Encoding.UTF8.GetBytes($"contacts:{settings.OrganizationId}:company-name:{label.ToLowerInvariant()}"));
            if (BitConverter.IsLittleEndian)
                Array.Reverse(digest, 0, sizeof(long));
            using var nameLock = new NpgsqlCommand("SELECT pg_advisory_xact_lock(@key)", db, tx);
            nameLock.Parameters.AddWithValue("key", BitConverter.ToInt64(digest, 0) & long.MaxValue);
            await nameLock.ExecuteNonQueryAsync();
        }
        using (var guard = RegisterCommand(@"SELECT CASE
            WHEN EXISTS (SELECT 1 FROM public.crm_companies WHERE organization_id=@company AND deleted_at IS NULL
                AND lower(trim(name))=lower(@label)) THEN 'Choose a unique label for the dedicated counter account.'
            WHEN EXISTS (SELECT 1 FROM public.crm_custom_fields WHERE organization_id=@company AND entity='companies'
                AND deleted_at IS NULL AND is_active AND is_required) THEN 'Required company custom fields prevent dedicated counter provisioning.'
            ELSE '' END", db, tx, branch, actor))
        {
            guard.Parameters.AddWithValue("label", label);
            if (await guard.ExecuteScalarAsync() is string error && error.Length != 0)
                throw new InvalidOperationException(error);
        }

        using var create = RegisterCommand(@"
            WITH party AS (
                INSERT INTO public.crm_companies (organization_id,branch_id,name,country,status,account_type,
                    notes,owner_user_id,created_by_user_id,updated_by_user_id,updated_at)
                VALUES (@company,@branch,@label,@country,'Active','Customer',
                    'Anonymous counter cash control ledger account. No named customer, personal address, contact or tax identity is asserted.',
                    @actor,@actor,@actor,now()) RETURNING id
            ), detail AS (
                INSERT INTO public.suite_company_master_details (account_id,organization_id,addresses,tax_registrations,version)
                SELECT id,@company,'[]','[]',1 FROM party
            ), relation AS (
                INSERT INTO public.suite_business_relationships (organization_id,account_id,role,status)
                SELECT @company,id,'Customer','Active' FROM party
            ), contact AS (
                INSERT INTO public.crm_contacts (organization_id,branch_id,company_id,full_name,first_name,status,
                    lifecycle_stage,tags_text,owner_user_id,created_by_user_id)
                SELECT @company,@branch,id,@label,left(split_part(@label,' ',1),100),'Active','Customer','Customer',@actor,@actor
                FROM party RETURNING id,company_id
            ), identity AS (
                INSERT INTO public.suite_contact_identity_links (organization_id,contact_id,account_id)
                SELECT @company,id,company_id FROM contact
            ), control AS (
                INSERT INTO public.srm_anonymous_cash_accounts (organization_id,branch_id,customer_id,jurisdiction_country,
                    account_label,active,created_by)
                SELECT @company,@branch,id,@country,@label,@active,@actor FROM party RETURNING id,customer_id
            ), audit AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,after_json)
                SELECT @company,'anonymous_cash_account',id,'configured',@actor,
                    json_build_object('id',id,'customer_id',customer_id,'revision',1,'active',@active,'reason',@reason)
                FROM control RETURNING id
            ), master_audit AS (
                INSERT INTO public.audit_logs (organization_id,user_id,method,endpoint,entity_type,entity_id,action,new_values,status_code)
                SELECT @company,@actor,'POST','/master-data','company',id,'COMPANY_MASTER_SAVED','{""roles"":[""Customer""]}',200
                FROM party
            ), owned AS (
                INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
                SELECT 'crm_companies',id::text,@company,@branch,'validated-write' FROM party
                UNION ALL SELECT 'crm_contacts',id::text,@company,@branch,'validated-write' FROM contact
                UNION ALL SELECT 'srm_anonymous_cash_accounts',id::text,@company,@branch,'validated-write' FROM control
                UNION ALL SELECT 'srm_audit_logs',id::text,@company,@branch,'validated-write' FROM audit
                RETURNING resource_key
            )
            SELECT id FROM control WHERE (SELECT count(*) FROM owned)=4", db, tx, branch, actor);
        create.Parameters.AddWithValue("label", label);
        create.Parameters.AddWithValue("country", country);
        create.Parameters.AddWithValue("active", enabled);
        create.Parameters.AddWithValue("reason", reason);
        if (await create.ExecuteScalarAsync() is not int)
            throw new InvalidOperationException("The dedicated counter account and its verified identity could not both be saved.");
    }

    private async Task SelectExistingPosAnonymousAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, int actor,
        int customer, string label, string country, bool enabled, string reason)
    {
        using var select = RegisterCommand(@"
            WITH party AS (
                SELECT c.id,c.owner_user_id,c.created_by_user_id FROM public.crm_companies c
                WHERE c.id=@customer AND c.organization_id=@company AND c.name=@label AND c.deleted_at IS NULL
                    AND c.account_type='Customer' AND c.status='Active'
                    AND " + ConfirmationOwnership("c", "crm_companies") + @"
                    AND NOT EXISTS(SELECT 1 FROM public.srm_sales_orders WHERE customer_id=c.id)
                    AND NOT EXISTS(SELECT 1 FROM public.srm_invoices WHERE customer_id=c.id)
                    AND NOT EXISTS(SELECT 1 FROM public.srm_receipts WHERE customer_id=c.id)
                    AND NOT EXISTS(SELECT 1 FROM public.srm_anonymous_cash_accounts WHERE customer_id=c.id)
                    AND NOT EXISTS(SELECT 1 FROM public.suite_contact_identity_links i
                        LEFT JOIN public.crm_contacts t ON t.id=i.contact_id
                        WHERE i.account_id=c.id AND (i.organization_id IS DISTINCT FROM @company
                            OR t.company_id IS DISTINCT FROM c.id OR t.deleted_at IS NOT NULL))
                FOR UPDATE OF c
            ), contact AS (
                INSERT INTO public.crm_contacts (organization_id,branch_id,company_id,full_name,first_name,status,
                    lifecycle_stage,tags_text,owner_user_id,created_by_user_id)
                SELECT @company,@branch,id,@label,left(split_part(@label,' ',1),100),'Active','Customer','Customer',
                    owner_user_id,created_by_user_id
                FROM party WHERE NOT EXISTS(SELECT 1 FROM public.suite_contact_identity_links WHERE account_id=party.id)
                RETURNING id,company_id
            ), identity AS (
                INSERT INTO public.suite_contact_identity_links (organization_id,contact_id,account_id)
                SELECT @company,id,company_id FROM contact
            ), control AS (
                INSERT INTO public.srm_anonymous_cash_accounts (organization_id,branch_id,customer_id,jurisdiction_country,
                    account_label,active,created_by)
                SELECT @company,@branch,id,@country,@label,@active,@actor FROM party RETURNING id,customer_id
            ), audit AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,after_json)
                SELECT @company,'anonymous_cash_account',id,'configured',@actor,
                    json_build_object('id',id,'customer_id',customer_id,'revision',1,'active',@active,'reason',@reason)
                FROM control RETURNING id
            ), owned AS (
                INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
                SELECT 'crm_contacts',id::text,@company,@branch,'validated-write' FROM contact
                UNION ALL SELECT 'srm_anonymous_cash_accounts',id::text,@company,@branch,'validated-write' FROM control
                UNION ALL SELECT 'srm_audit_logs',id::text,@company,@branch,'validated-write' FROM audit RETURNING resource_key
            )
            SELECT id FROM control WHERE (SELECT count(*) FROM owned)=2+(SELECT count(*) FROM contact)", db, tx, branch, actor);
        select.Parameters.AddWithValue("customer", customer);
        select.Parameters.AddWithValue("label", label);
        select.Parameters.AddWithValue("country", country);
        select.Parameters.AddWithValue("active", enabled);
        select.Parameters.AddWithValue("reason", reason);
        if (await select.ExecuteScalarAsync() is not int)
            throw new InvalidOperationException("Choose an active, unused dedicated Customer ledger in this branch with the matching label.");
    }
}
