using System.Data;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record LeadConversion(int? Contact, int? Company, bool Individual, bool CreateDeal, string DealName);
internal sealed record LeadConversionResult(int Company, int Contact, int? Deal);
internal sealed record LeadConversionChoices(List<CrmLookup> Companies, List<CrmLookup> Contacts, int? LinkedContact);

internal static partial class LeadStore
{
    internal static async Task<LeadConversionChoices> ReadConversionChoices(DataRow row, CancellationToken cancellation)
    {
        var settings = DesktopDatabaseSettings.Load();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await CrmDirectoryWrites.RequireCrmActorAsync(settings, db, tx, cancellation, "leads", "convert");
        await CrmDirectoryWrites.RequireCrmAccessAsync(settings, db, tx, actor, "accounts", "view");
        await CrmDirectoryWrites.RequireCrmAccessAsync(settings, db, tx, actor, "contacts", "view");
        var companies = await ReadChoices("crm_companies", "name", "Create or match a company");
        var contacts = await ReadChoices("crm_contacts", "full_name", "Create a contact");
        using var link = Cmd(db, tx,
            "SELECT contact_id FROM public.suite_contact_identity_links WHERE organization_id=@org AND lead_id=@id",
            ("org", NpgsqlDbType.Integer, settings.OrganizationId), ("id", NpgsqlDbType.Integer, (int)row["id"]));
        int? identity = await link.ExecuteScalarAsync(cancellation) as int?;
        return new(companies, contacts, identity);

        async Task<List<CrmLookup>> ReadChoices(string table, string name, string automatic)
        {
            var options = new List<CrmLookup> { new(null, automatic) };
            using var query = Cmd(db, tx,
                $"SELECT id,{name} FROM public.{table} r WHERE organization_id=@org AND deleted_at IS NULL AND " +
                CrmDirectoryWrites.BranchScope(table, "r") + $" ORDER BY {name},id",
                ("org", NpgsqlDbType.Integer, settings.OrganizationId), ("scope_branch", NpgsqlDbType.Integer, settings.BranchId));
            using var reader = await query.ExecuteReaderAsync(cancellation);
            while (await reader.ReadAsync(cancellation))
                options.Add(new(reader.GetInt32(0), $"{reader.GetString(1)}  (#{reader.GetInt32(0)})"));
            return options;
        }
    }

    internal static async Task<LeadConversionResult> ConvertAsync(LeadKey key, LeadConversion request,
        CancellationToken cancellation)
    {
        if (key.Potential)
            throw new InvalidOperationException("Convert the potential client to a lead first.");
        if (request.DealName.Length > 180)
            throw new ArgumentException("Enter a deal name of up to 180 characters.");
        var settings = DesktopDatabaseSettings.Load();
        int org = settings.OrganizationId;
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.Serializable);
        var actor = await settings.VerifyWriteTargetAsync(db, tx, cancellation);
        await CrmDirectoryWrites.RequireCrmAccessAsync(settings, db, tx, actor, "leads", "convert");
        await CrmDirectoryWrites.RequireCrmAccessAsync(settings, db, tx, actor, "accounts", "view");
        await CrmDirectoryWrites.RequireCrmAccessAsync(settings, db, tx, actor, "contacts", "view");
        if (request.CreateDeal)
            await CrmDirectoryWrites.RequireCrmAccessAsync(settings, db, tx, actor, "deals", "create");
        DataRow lead = await LockLead(db, tx, settings, key, false, cancellation);
        if (Text(lead, "status") != "Qualified" || lead["is_converted"] is true)
            throw new InvalidOperationException("Qualify the lead before converting it.");
        LeadPolicy policy = await ReadPolicy(db, tx, org, cancellation);
        var detail = ReadDetails(lead);
        ValidateTransition(policy, lead, "Converted", new(), detail, true);

        int branch = lead["branch_id"] is int existingBranch
            ? await CrmDirectoryWrites.CreationBranch(db, tx, settings, existingBranch, cancellation)
            : await CrmDirectoryWrites.CreationBranch(db, tx, settings, null, cancellation);
        int? contactId = request.Contact;
        int? companyId = request.Company;
        using (var link = LeadCommand("SELECT contact_id FROM public.suite_contact_identity_links WHERE organization_id=@org AND lead_id=@lead"))
        {
            if (await link.ExecuteScalarAsync(cancellation) is int knownContact)
            {
                if (contactId.HasValue && contactId.Value != knownContact)
                    throw new InvalidOperationException("This lead already has a linked contact. Select that contact to convert.");
                contactId = knownContact;
            }
        }
        string? primaryPhone = Text(lead, "phone").Length == 0 ? null :
            CrmPhone.Normalize(Text(lead, "phone"), Text(lead, "phone_country_code")).International;

        if (contactId.HasValue)
        {
            await RequireRelated(db, tx, settings, "crm_contacts", contactId.Value, cancellation);
            using var ownership = LeadCommand("SELECT company_id FROM public.crm_contacts WHERE organization_id=@org AND id=@id",
                ("id", NpgsqlDbType.Integer, contactId));
            if (await ownership.ExecuteScalarAsync(cancellation) is int linkedCompany)
            {
                if (companyId.HasValue && companyId.Value != linkedCompany)
                    throw new InvalidOperationException("The selected contact is linked to a different company.");
                companyId = linkedCompany;
            }
        }
        else
        {
            using var duplicates = LeadCommand(@"SELECT c.id FROM public.crm_contacts c
                WHERE c.organization_id=@org AND c.deleted_at IS NULL AND "+CrmDirectoryWrites.PublicPartyScope("crm_contacts","c")+@" AND (
                    (@email<>'' AND lower(trim(c.email))=lower(@email))
                    OR (@phone IS NOT NULL AND (
                        CASE WHEN c.phone LIKE '+%' THEN regexp_replace(c.phone,'[ ().-]','','g')
                             ELSE c.phone_country_code || regexp_replace(c.phone,'[ ().-]','','g') END = @phone
                        OR EXISTS (SELECT 1 FROM public.suite_contact_channels ch WHERE ch.organization_id=@org
                            AND ch.contact_id=c.id AND ch.kind='phone' AND ch.normalized_value=@phone))))
                ORDER BY c.id LIMIT 1",
                ("email", NpgsqlDbType.Text, Text(lead, "email")), ("phone", NpgsqlDbType.Text, primaryPhone));
            if (await duplicates.ExecuteScalarAsync(cancellation) is int duplicate)
                throw new InvalidOperationException($"Matching contact #{duplicate} exists. Select it in the conversion dialog.");
        }

        string companyName = request.Individual ? Text(lead, "full_name") : Text(lead, "company_name");
        if (companyName.Length == 0)
            companyName = Text(lead, "full_name");
        if (companyName.Length > 180 && companyId is null)
            throw new ArgumentException("The destination company name is over 180 characters. Select an existing company or shorten the lead name.");

        if (!companyId.HasValue && !request.Individual)
        {
            using var find = LeadCommand(@"SELECT id FROM public.crm_companies c
                WHERE organization_id=@org AND deleted_at IS NULL AND lower(trim(name))=lower(@name) AND "+
                CrmDirectoryWrites.PublicPartyScope("crm_companies","c")+@"
                ORDER BY id LIMIT 2", ("name", NpgsqlDbType.Text, companyName));
            using var reader = await find.ExecuteReaderAsync(cancellation);
            if (await reader.ReadAsync(cancellation))
            {
                companyId = reader.GetInt32(0);
                if (await reader.ReadAsync(cancellation))
                    throw new InvalidOperationException("Several companies match. Select the correct company explicitly.");
            }
        }

        bool newCompany = !companyId.HasValue;
        await CrmDirectoryWrites.RequireCrmAccessAsync(settings, db, tx, actor, "accounts", newCompany ? "create" : "edit");
        string companyRole = policy.SalesProcess ? "Prospect" : "Customer";
        string lifecycle = policy.SalesProcess ? "Opportunity" : "Customer";
        if (newCompany)
        {
            await CrmDirectoryWrites.CheckReservedCompanyNameAsync(db,tx,org,companyName,cancellation);
            using var insert = LeadCommand(@"INSERT INTO public.crm_companies
                (organization_id,branch_id,owner_user_id,department_id,assigned_team_id,name,industry,website,
                 phone,phone_country_code,email,address,city,state,country,employee_count,account_type,status,
                 services_offered,business_types,updated_at)
                SELECT @org,@branch,owner_user_id,department_id,assigned_team_id,@name,industry,
                    COALESCE(company_website,website),phone,phone_country_code,email,address,city,state,country,employee_count,
                    @role,'Active',services_offered,business_types,now()
                FROM public.crm_leads WHERE organization_id=@org AND id=@lead RETURNING id",
                ("name", NpgsqlDbType.Text, companyName), ("role", NpgsqlDbType.Text, companyRole));
            companyId = (int)(await insert.ExecuteScalarAsync(cancellation))!;
            await AddOwnership(db, tx, org, "crm_companies", companyId.Value, branch, cancellation);
            using var master = LeadCommand(@"INSERT INTO public.suite_company_master_details
                (account_id,organization_id,business_type,addresses,tax_registrations,version)
                VALUES (@company,@org,@type,'[]'::json,'[]'::json,1)", ("company", NpgsqlDbType.Integer, companyId),
                ("type", NpgsqlDbType.Text, request.Individual ? "Individual" : null));
            await master.ExecuteNonQueryAsync(cancellation);
        }
        else
        {
            await RequireRelated(db, tx, settings, "crm_companies", companyId!.Value, cancellation);
            using var name = LeadCommand("SELECT name FROM public.crm_companies WHERE organization_id=@org AND id=@company",
                ("company", NpgsqlDbType.Integer, companyId));
            companyName = (string)(await name.ExecuteScalarAsync(cancellation))!;
        }

        bool newContact = !contactId.HasValue;
        await CrmDirectoryWrites.RequireCrmAccessAsync(settings, db, tx, actor, "contacts", newContact ? "create" : "edit");
        if (newContact)
        {
            using var insert = LeadCommand(@"INSERT INTO public.crm_contacts
                (organization_id,branch_id,owner_user_id,department_id,assigned_team_id,company_id,company_name,
                 first_name,last_name,full_name,email,phone,phone_country_code,alternate_phone,alternate_phone_country_code,
                 job_title,lifecycle_stage,source,industry,website,company_website,linkedin_url,employee_count,
                 city,state,country,address,services_offered,business_types,status,customer_since,tags_text,updated_at)
                SELECT @org,@branch,owner_user_id,department_id,assigned_team_id,@company,@name,
                 first_name,last_name,full_name,email,phone,phone_country_code,alternate_phone,alternate_phone_country_code,
                 job_title,@stage,source,industry,website,company_website,linkedin_url,employee_count,
                 city,state,country,address,services_offered,business_types,'Active',
                 CASE WHEN @stage='Customer' THEN current_date ELSE NULL END,'Lead, ' || @stage,now()
                FROM public.crm_leads WHERE organization_id=@org AND id=@lead RETURNING id",
                ("company", NpgsqlDbType.Integer, companyId), ("name", NpgsqlDbType.Text, companyName),
                ("stage", NpgsqlDbType.Text, lifecycle));
            contactId = (int)(await insert.ExecuteScalarAsync(cancellation))!;
            await AddOwnership(db, tx, org, "crm_contacts", contactId.Value, branch, cancellation);
        }
        int company = companyId!.Value;
        int contact = contactId!.Value;
        using (var update = LeadCommand(@"UPDATE public.crm_contacts SET company_id=COALESCE(company_id,@company),
                company_name=CASE WHEN company_id IS NULL THEN @company_name ELSE company_name END,
                lifecycle_stage=CASE WHEN lifecycle_stage='Customer' THEN lifecycle_stage ELSE @stage END,
                customer_since=CASE WHEN lifecycle_stage='Customer' OR @stage='Customer' THEN COALESCE(customer_since,current_date) ELSE customer_since END,
                tags_text=(SELECT string_agg(DISTINCT tag, ', ' ORDER BY tag) FROM
                  (SELECT trim(value) AS tag FROM unnest(string_to_array(COALESCE(tags_text,''),',')) value
                   UNION SELECT 'Lead' UNION SELECT CASE WHEN lifecycle_stage='Customer' THEN 'Customer' ELSE @stage END) tags WHERE tag<>''),
                updated_at=now() WHERE organization_id=@org AND id=@contact",
            ("company", NpgsqlDbType.Integer, company), ("contact", NpgsqlDbType.Integer, contact),
            ("stage", NpgsqlDbType.Text, lifecycle), ("company_name", NpgsqlDbType.Text, companyName)))
            await update.ExecuteNonQueryAsync(cancellation);

        using (var update = LeadCommand(@"UPDATE public.crm_companies SET
                account_type=CASE WHEN account_type='Customer' THEN account_type ELSE @role END,updated_at=now()
                WHERE organization_id=@org AND id=@company",
                ("company", NpgsqlDbType.Integer, company), ("role", NpgsqlDbType.Text, companyRole)))
            await update.ExecuteNonQueryAsync(cancellation);
        using (var relationship = LeadCommand(@"INSERT INTO public.suite_business_relationships
            (organization_id,account_id,role,status)
            SELECT organization_id,id,account_type,'Active' FROM public.crm_companies
            WHERE organization_id=@org AND id=@company ON CONFLICT (account_id,role) DO NOTHING",
            ("company", NpgsqlDbType.Integer, company)))
            await relationship.ExecuteNonQueryAsync(cancellation);

        using (var identity = LeadCommand(@"INSERT INTO public.suite_contact_identity_links (organization_id,contact_id,lead_id)
                VALUES (@org,@contact,@lead) ON CONFLICT (lead_id) DO NOTHING",
                ("contact", NpgsqlDbType.Integer, contact)))
            await identity.ExecuteNonQueryAsync(cancellation);

        if (newCompany)
        {
            using var identity = LeadCommand(@"INSERT INTO public.suite_contact_identity_links (organization_id,contact_id,account_id)
                VALUES (@org,@contact,@company)", ("contact", NpgsqlDbType.Integer, contact), ("company", NpgsqlDbType.Integer, company));
            await identity.ExecuteNonQueryAsync(cancellation);
        }
        if (primaryPhone is not null && (newCompany || newContact))
        {
            var phone = CrmPhone.Normalize(Text(lead, "phone"), Text(lead, "phone_country_code"));
            if (newCompany) await CrmExtrasWrites.EnsurePrimaryPhoneAsync(db, tx, org, company, true, phone, cancellation);
            if (newContact) await CrmExtrasWrites.EnsurePrimaryPhoneAsync(db, tx, org, contact, false, phone, cancellation);
        }

        int? deal = null;
        if (request.CreateDeal)
        {
            using var insert = LeadCommand(@"WITH entry AS (
                SELECT p.id AS pipeline, s.id AS stage, COALESCE(s.probability,0) AS probability
                FROM public.crm_pipelines p JOIN public.crm_pipeline_stages s ON s.pipeline_id=p.id
                WHERE p.organization_id=@org AND p.deleted_at IS NULL AND p.active IS TRUE
                  AND (@pipeline IS NULL OR p.id=@pipeline)
                  AND (s.organization_id IS NULL OR s.organization_id=@org) AND s.deleted_at IS NULL AND s.active IS TRUE
                  AND COALESCE(s.is_won,false)=false AND COALESCE(s.is_lost,false)=false
                  AND COALESCE(lower(s.stage_type),'open') NOT IN ('won','lost')
                ORDER BY p.is_default DESC NULLS LAST,p.id,s.position NULLS LAST,s.id LIMIT 1 FOR SHARE OF p,s)
                INSERT INTO public.crm_deals (organization_id,branch_id,owner_user_id,department_id,assigned_team_id,
                    company_id,contact_id,pipeline_id,stage_id,name,amount,currency,probability,expected_revenue,
                    expected_close_date,status,lead_source,source,next_follow_up_at,tags_text,position,updated_at)
                SELECT @org,@branch,l.owner_user_id,l.department_id,l.assigned_team_id,@company,@contact,
                    entry.pipeline,entry.stage,@name,COALESCE(l.estimated_value,0),
                    COALESCE(c.default_currency,'INR'),entry.probability,COALESCE(l.estimated_value,0)*entry.probability/100,
                    l.expected_close_date,'Open',l.source,l.source,l.next_follow_up_at,l.tags_text,0,now()
                FROM public.crm_leads l JOIN public.companies c ON c.id=l.organization_id CROSS JOIN entry
                WHERE l.organization_id=@org AND l.id=@lead RETURNING id",
                ("company", NpgsqlDbType.Integer, company), ("contact", NpgsqlDbType.Integer, contact),
                ("name", NpgsqlDbType.Text, request.DealName.Length == 0
                    ? (companyName.Length > 168 ? companyName.Substring(0, 168) : companyName) + " opportunity" : request.DealName),
                ("pipeline", NpgsqlDbType.Integer, policy.PipelineId));
            deal = await insert.ExecuteScalarAsync(cancellation) as int?;
            if (!deal.HasValue)
                throw new InvalidOperationException("Create an active CRM pipeline and open stage before converting to a deal.");
            await AddOwnership(db, tx, org, "crm_deals", deal.Value, branch, cancellation);
            using var stakeholder = LeadCommand(@"INSERT INTO public.crm_deal_contacts
                (organization_id,deal_id,contact_id,role,is_primary) VALUES (@org,@deal,@contact,'Stakeholder',true)",
                ("deal", NpgsqlDbType.Integer, deal), ("contact", NpgsqlDbType.Integer, contact));
            await stakeholder.ExecuteNonQueryAsync(cancellation);
        }

        await StopSequence(db, tx, org, key.Id, detail, "Converted", cancellation);
        detail["stageEnteredAt"] = DateTimeOffset.UtcNow.ToString("o");
        await WriteState(db, tx, org, key.Id, detail, key.StateRevision, cancellation);
        using (var update = LeadCommand(@"UPDATE public.crm_leads SET is_converted=true,converted_at=now(),
            status='Converted',converted_company_id=@company,converted_contact_id=@contact,converted_deal_id=@deal,updated_at=now()
            WHERE organization_id=@org AND id=@lead", ("company", NpgsqlDbType.Integer, company),
            ("contact", NpgsqlDbType.Integer, contact), ("deal", NpgsqlDbType.Integer, deal)))
            await update.ExecuteNonQueryAsync(cancellation);
        using (var log = LeadCommand(@"INSERT INTO public.crm_lead_conversion_logs
            (organization_id,lead_id,converted_account_id,converted_contact_id,converted_deal_id,converted_by_user_id,conversion_status,notes)
            VALUES (@org,@lead,@company,@contact,@deal,@actor,'completed','Converted in Business Suite Desktop')",
            ("actor", NpgsqlDbType.Integer, actor.Id), ("company", NpgsqlDbType.Integer, company), ("contact", NpgsqlDbType.Integer, contact), ("deal", NpgsqlDbType.Integer, deal)))
            await log.ExecuteNonQueryAsync(cancellation);
        using (var activity = LeadCommand(@"INSERT INTO public.crm_activities
            (organization_id,branch_id,entity_type,entity_id,lead_id,activity_type,title,subject,body,status,activity_date,metadata_json)
            VALUES (@org,@branch,'lead',@lead,@lead,'conversion','Lead converted','Lead converted',
                'Lead converted into CRM customer records.','Completed',now(),@metadata) RETURNING id",
            ("metadata", NpgsqlDbType.Json, JsonSerializer.Serialize(new { contactId = contact, companyId = company, dealId = deal }))))
        {
            int activityId = (int)(await activity.ExecuteScalarAsync(cancellation))!;
            await AddOwnership(db, tx, org, "crm_activities", activityId, branch, cancellation);
        }
        await CrmDirectoryWrites.Audit(db, tx, "crm_leads", org, key.Id, actor.Id, "CONVERT", cancellation);
        tx.Commit();
        return new(company, contact, deal);

        NpgsqlCommand LeadCommand(string sql, params (string, NpgsqlDbType, object?)[] values) =>
            Cmd(db, tx, sql, new (string, NpgsqlDbType, object?)[]
            {
                ("org", NpgsqlDbType.Integer, org), ("lead", NpgsqlDbType.Integer, key.Id), ("branch", NpgsqlDbType.Integer, branch)
            }.Concat(values).ToArray());
    }
    private static async Task StopSequence(NpgsqlConnection db, NpgsqlTransaction tx, int organization, int leadId,
        Dictionary<string, object?> detail, string reason, CancellationToken cancellation)
    {
        if (detail.TryGetValue("sequence", out object? rawSequence) && rawSequence is JsonElement sequence &&
            sequence.ValueKind == JsonValueKind.Object && sequence.TryGetProperty("active", out JsonElement active) &&
            active.ValueKind == JsonValueKind.True)
        {
            var stopped = sequence.EnumerateObject().ToDictionary(property => property.Name, property => (object?)property.Value.Clone());
            stopped["active"] = false;
            stopped["stoppedAt"] = DateTimeOffset.UtcNow.ToString("o");
            stopped["stopReason"] = reason;
            detail["sequence"] = stopped;
            if (sequence.TryGetProperty("id", out var sequenceId))
            {
                using var cancel = Cmd(db, tx, @"UPDATE public.crm_activities SET status='Cancelled',updated_at=now()
                    WHERE organization_id=@org AND lead_id=@lead AND status='Pending' AND metadata_json->>'sequenceId'=@sequence",
                    ("org", NpgsqlDbType.Integer, organization), ("lead", NpgsqlDbType.Integer, leadId),
                    ("sequence", NpgsqlDbType.Text, sequenceId.ToString()));
                await cancel.ExecuteNonQueryAsync(cancellation);
            }
        }
    }
}
