using Npgsql;

namespace Business_Suite;

internal sealed record SalesEngagementProject(int Id, string Key);

internal sealed partial class SalesOrderRepository
{
    internal async Task<SalesEngagementProject?> CreateEngagementProjectAsync(int order, int engagement)
    {
        int branch = settings.BranchId ?? throw new UnauthorizedAccessException("Choose a branch for project handoff.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync();
        using var tx = db.BeginTransaction();
        await settings.VerifyWriteTargetAsync(db, tx, CancellationToken.None);
        await LockCompanyWriterAsync(db, tx);
        var actor = await settings.RequireActorAsync(db, tx, CancellationToken.None);
        if (!actor.CanWriteBranch)
            throw new UnauthorizedAccessException("This branch is read-only for the signed-in user.");
        await RequireNativeRegisterBranchAsync(db, tx, branch, "engagement project handoff");
        string scope = await SalesReadAccess.OrderScopeAsync(db, tx, settings.OrganizationId, branch, actor, "create");
        using var read = ScopedCommand(@"
            SELECT coalesce(e.status,''),coalesce(o.status,''),e.pms_project_id,
                coalesce(o.metadata_json->>'seller_id',@company::text)=@company::text,
                e.customer_id,coalesce(e.project_manager_user_id,@actor),coalesce(e.assigned_user_id,@actor)
            FROM public.srm_sales_orders o JOIN public.srm_engagements e ON e.sales_order_id=o.id" +
            NativeSalesEngagementScope + " AND e.id=@engagement FOR UPDATE OF o,e", db, tx, branch, actor, scope);
        read.Parameters.AddWithValue("order", order);
        read.Parameters.AddWithValue("engagement", engagement);
        int? existing;
        int? customer;
        int manager;
        int owner;
        bool seller;
        string orderStatus;
        using (var rows = await read.ExecuteReaderAsync())
        {
            if (!await rows.ReadAsync())
                throw new InvalidOperationException("The engagement is unavailable in the selected branch.");
            if (rows.GetString(0) is "closed" or "cancelled")
                throw new InvalidOperationException("Closed or cancelled engagements cannot create delivery projects.");
            orderStatus = rows.GetString(1);
            existing = rows.IsDBNull(2) ? null : rows.GetInt32(2);
            seller = rows.GetBoolean(3);
            customer = rows.IsDBNull(4) ? null : rows.GetInt32(4);
            manager = rows.GetInt32(5);
            owner = rows.GetInt32(6);
        }
        using (var entitlement = RegisterCommand("SELECT enabled FROM public.bos_enabled_modules WHERE company_id=@company " +
            "AND module_key='project_management' FOR SHARE", db, tx, branch, actor.Id))
        {
            if (await entitlement.ExecuteScalarAsync() is false)
            {
                await RecordSkippedProjectHandoffAsync(db, tx, branch, actor.Id, engagement);
                tx.Commit();
                return null;
            }
        }
        if (existing is int project)
        {
            using var find = RegisterCommand(@"SELECT p.project_key FROM public.pms_projects p
                WHERE p.id=@project AND p.organization_id=@company AND p.deleted_at IS NULL AND " +
                ConfirmationOwnership("p", "pms_projects"), db, tx, branch, actor.Id);
            find.Parameters.AddWithValue("project", project);
            if (await find.ExecuteScalarAsync() is not string key)
                throw new InvalidOperationException("The linked delivery project is unavailable in this branch.");
            tx.Commit();
            return new SalesEngagementProject(project, key);
        }
        if (orderStatus != "confirmed")
            throw new InvalidOperationException("Confirm the source Sales order before creating a delivery project.");
        if (!seller)
            throw new InvalidOperationException("An alternate legal seller requires its verified sales handoff.");
        await VerifyEngagementProjectSourcesAsync(db, tx, branch, actor, order, engagement, customer, manager, owner);
        var saved = await SaveEngagementProjectAsync(db, tx, branch, actor.Id, order, engagement, manager, owner);
        tx.Commit();
        return saved;
    }

    private async Task RecordSkippedProjectHandoffAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, int actor, int engagement)
    {
        using var command = RegisterCommand(@"
            WITH skipped AS (
                INSERT INTO public.bos_lifecycle_events (company_id,module_key,entity_type,entity_id,event_name,status,
                    message,source_module,target_module,actor_user_id)
                SELECT @company,'srm','engagement',@engagement::text,'srm_pms_handoff_skipped','skipped',
                    'PMS is not enabled','srm','project_management',@actor
                WHERE NOT EXISTS (SELECT 1 FROM public.bos_lifecycle_events v WHERE v.company_id=@company
                    AND v.entity_type='engagement' AND v.entity_id=@engagement::text AND v.event_name='srm_pms_handoff_skipped')
                RETURNING id
            )
            INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
            SELECT 'bos_lifecycle_events',id::text,@company,@branch,'validated-write' FROM skipped", db, tx, branch, actor);
        command.Parameters.AddWithValue("engagement", engagement);
        await command.ExecuteNonQueryAsync();
    }

    private async Task VerifyEngagementProjectSourcesAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch, DesktopActor actor,
        int order, int engagement, int? customer, int manager, int owner)
    {
        using (var lockLines = RegisterCommand("SELECT id FROM public.srm_sales_order_lines WHERE sales_order_id=@order " +
            "ORDER BY id FOR UPDATE NOWAIT", db, tx, branch, actor.Id))
        {
            lockLines.Parameters.AddWithValue("order", order);
            await lockLines.ExecuteNonQueryAsync();
        }
        if (customer is int buyer)
        {
            using var find = RegisterCommand("SELECT c.id FROM public.crm_companies c" + OrderCustomerScope +
                " AND c.id=@buyer FOR SHARE OF c", db, tx, branch, actor.Id);
            find.Parameters.AddWithValue("buyer", buyer);
            if (await find.ExecuteScalarAsync() is not int)
                throw new InvalidOperationException("The linked project customer is unavailable in this branch.");
        }
        using var gate = RegisterCommand(@"
            SELECT (SELECT count(*) FROM public.users u WHERE u.id IN (@manager,@owner) AND u.is_active
                AND (u.id=@actor OR EXISTS (
                    SELECT 1 FROM public.suite_access_memberships m WHERE m.user_id=u.id AND m.company_id=@company AND m.active)
                    OR EXISTS (SELECT 1 FROM public.suite_branch_grants g WHERE g.user_id=u.id AND g.company_id=@company AND g.branch_id=@branch)))
                    = CASE WHEN @manager=@owner THEN 1 ELSE 2 END
                AND NOT EXISTS (SELECT 1 FROM public.srm_sales_order_lines l WHERE l.sales_order_id=@order
                    AND NOT (" + ConfirmationOwnership("l", "srm_sales_order_lines") + @"))
                AND NOT EXISTS (SELECT 1 FROM public.srm_billing_plans p WHERE p.engagement_id=@engagement
                    AND (p.organization_id IS DISTINCT FROM @company OR NOT (" + ConfirmationOwnership("p", "srm_billing_plans") + @")))
                AND NOT EXISTS (SELECT 1 FROM public.srm_billing_milestones m
                    JOIN public.srm_billing_plans p ON p.id=m.billing_plan_id WHERE p.engagement_id=@engagement
                    AND (NOT (" + ConfirmationOwnership("m", "srm_billing_milestones") + @")
                        OR EXISTS (SELECT 1 FROM public.business_milestone_billing_sources s WHERE s.billing_milestone_id=m.id)))
                AND NOT EXISTS (SELECT 1 FROM public.srm_billing_milestones m
                    JOIN public.srm_billing_plans p ON p.id=m.billing_plan_id WHERE p.engagement_id=@engagement
                    AND m.metadata_json->>'sales_order_line_id' IS NOT NULL
                    GROUP BY m.metadata_json->>'sales_order_line_id' HAVING count(*)>1)", db, tx, branch, actor.Id);
        gate.Parameters.AddWithValue("order", order);
        gate.Parameters.AddWithValue("engagement", engagement);
        gate.Parameters.AddWithValue("manager", manager);
        gate.Parameters.AddWithValue("owner", owner);
        if (await gate.ExecuteScalarAsync() is not true)
            throw new InvalidOperationException("Verify the Sales order lines, project assignees and billing milestone sources before starting delivery.");
    }

    private async Task<SalesEngagementProject> SaveEngagementProjectAsync(NpgsqlConnection db, NpgsqlTransaction tx, int branch,
        int actor, int order, int engagement, int manager, int owner)
    {
        using var write = RegisterCommand(@"
            WITH source AS (
                SELECT e.*,o.crm_contact_id FROM public.srm_engagements e JOIN public.srm_sales_orders o ON o.id=e.sales_order_id
                WHERE e.id=@engagement AND o.id=@order
            ), project AS (
                INSERT INTO public.pms_projects (organization_id,branch_id,manager_user_id,owner_user_id,name,project_key,
                    category,description,status,budget_amount,billing_status,is_client_visible,priority,health)
                SELECT @company,@branch,@manager,@owner,left(name,180),'SRM'||id,'SRM Engagement',
                    'Created from SRM engagement '||engagement_number,'Active',budget_amount,'Unbilled',true,'Medium','Good'
                FROM source RETURNING id,project_key
            ), manager_member AS (
                INSERT INTO public.pms_project_members (project_id,user_id,role,allocation_percent)
                SELECT id,@manager,'Project Manager',100 FROM project RETURNING id
            ), kickoff AS (
                INSERT INTO public.pms_milestones (project_id,owner_user_id,name,status,progress_percent,client_approval_status)
                SELECT id,@manager,'Kickoff','Not Started',0,'Not Required' FROM project RETURNING id
            ), ordered_items AS MATERIALIZED (
                SELECT l.id, nullif(l.description,'') AS description, row_number() OVER(ORDER BY l.id) AS ordinal,
                    nextval(pg_get_serial_sequence('public.pms_milestones','id'))::int AS delivery_id
                FROM public.srm_sales_order_lines l WHERE l.sales_order_id=@order
            ), delivery AS (
                INSERT INTO public.pms_milestones (id,project_id,owner_user_id,name,status,progress_percent,client_approval_status)
                SELECT l.delivery_id,p.id,@manager,left(coalesce(l.description,'Commercial line '||l.ordinal),180),
                    'Not Started',0,'Not Required' FROM ordered_items l CROSS JOIN project p RETURNING id
            ), task AS (
                INSERT INTO public.pms_tasks (project_id,milestone_id,assignee_user_id,reporter_user_id,title,description,task_key,
                    status,priority,estimated_hours,is_client_visible,work_type,security_level)
                SELECT p.id,d.id,@manager,@actor,left(coalesce(l.description,'Deliver service line '||l.ordinal),220),
                    'Created from SRM sales order line '||l.id,p.project_key||'-'||l.ordinal,
                    'To Do','Medium',8,true,'Task','Internal'
                FROM ordered_items l JOIN delivery d ON d.id=l.delivery_id CROSS JOIN project p RETURNING id
            ), bill_source AS (
                INSERT INTO public.business_milestone_billing_sources (pms_milestone_id,billing_milestone_id)
                SELECT d.id,m.id FROM ordered_items l JOIN delivery d ON d.id=l.delivery_id
                JOIN public.srm_billing_plans b ON b.engagement_id=@engagement
                JOIN public.srm_billing_milestones m ON m.billing_plan_id=b.id AND m.metadata_json->>'sales_order_line_id'=l.id::text
                RETURNING pms_milestone_id AS id
            ), commercial AS (
                INSERT INTO public.business_project_commercial (project_id,customer_id,seller_id,contact_id,team_id,currency,
                    opportunity_id,sales_order_id,engagement_id,updated_by)
                SELECT p.id,s.customer_id,@company,contact.id,team.id,s.currency,deal.id,@order,s.id,@actor
                FROM project p CROSS JOIN source s JOIN public.crm_companies buyer ON buyer.id=s.customer_id
                LEFT JOIN public.crm_contacts contact ON contact.id=s.crm_contact_id AND contact.company_id=buyer.id
                    AND contact.organization_id=@company AND contact.deleted_at IS NULL AND " + ConfirmationOwnership("contact", "crm_contacts") + @"
                LEFT JOIN public.business_sales_team_assignments a ON a.sales_order_id=@order
                LEFT JOIN public.crm_teams team ON team.id=coalesce(a.team_id,buyer.assigned_team_id) AND team.organization_id=@company
                LEFT JOIN public.crm_deals deal ON deal.id=s.crm_deal_id AND deal.organization_id=@company
                    AND deal.deleted_at IS NULL AND " + ConfirmationOwnership("deal", "crm_deals") + @"
                RETURNING project_id AS id
            ), updated AS (
                UPDATE public.srm_engagements e SET pms_project_id=p.id,status='project_created',updated_at=now()
                FROM project p WHERE e.id=@engagement RETURNING e.id
            ), link AS (
                INSERT INTO public.srm_engagement_links (engagement_id,linked_module,linked_entity_type,linked_entity_id,label)
                SELECT e.id,'project_management','project',p.id,p.project_key FROM updated e CROSS JOIN project p RETURNING id
            ), audit AS (
                INSERT INTO public.srm_audit_logs (organization_id,entity_type,entity_id,action,actor_user_id,after_json)
                SELECT @company,'engagement',e.id,'pms_project_created',@actor,json_build_object('pms_project_id',p.id)
                FROM updated e CROSS JOIN project p RETURNING id
            ), notice AS (
                INSERT INTO public.notifications (company_id,user_id,title,message,module,event_type,related_entity_type,
                    related_entity_id,action_url,priority,channels,is_read)
                SELECT @company,@manager,'PMS project created',p.project_key||' was created from SRM engagement '||s.engagement_number,
                    'srm','srm.lifecycle','project',p.id,'/pms/projects/'||p.id,'normal',json_build_array('in_app'),false
                FROM project p CROSS JOIN source s
                UNION ALL SELECT @company,s.assigned_user_id,'SRM engagement linked to PMS',s.engagement_number||' is linked to PMS project '||p.project_key,
                    'srm','srm.lifecycle','engagement',s.id,'/srm/engagements/'||s.id,'normal',json_build_array('in_app'),false
                FROM project p CROSS JOIN source s WHERE s.assigned_user_id IS NOT NULL RETURNING id
            ), stamp AS (
                INSERT INTO public.suite_branch_ownership (resource_table,resource_key,company_id,branch_id,source)
                SELECT resource,id::text,@company,@branch,'validated-write' FROM (
                    SELECT 'pms_projects' AS resource,id FROM project UNION ALL
                    SELECT 'pms_project_members',id FROM manager_member UNION ALL
                    SELECT 'pms_milestones',id FROM kickoff UNION ALL SELECT 'pms_milestones',id FROM delivery UNION ALL
                    SELECT 'pms_tasks',id FROM task UNION ALL SELECT 'business_milestone_billing_sources',id FROM bill_source UNION ALL
                    SELECT 'business_project_commercial',id FROM commercial UNION ALL
                    SELECT 'srm_engagement_links',id FROM link UNION ALL SELECT 'srm_audit_logs',id FROM audit UNION ALL
                    SELECT 'notifications',id FROM notice
                ) owned RETURNING resource_key
            )
            SELECT id,project_key FROM project WHERE (SELECT count(*) FROM updated)=1
                AND (SELECT count(*) FROM delivery)=(SELECT count(*) FROM ordered_items)
                AND (SELECT count(*) FROM task)=(SELECT count(*) FROM ordered_items)
                AND (SELECT count(*) FROM stamp)>=6", db, tx, branch, actor);
        write.Parameters.AddWithValue("order", order);
        write.Parameters.AddWithValue("engagement", engagement);
        write.Parameters.AddWithValue("manager", manager);
        write.Parameters.AddWithValue("owner", owner);
        using var rows = await write.ExecuteReaderAsync();
        if (!await rows.ReadAsync())
            throw new InvalidOperationException("The project, engagement link and delivery work could not all be saved.");
        return new SalesEngagementProject(rows.GetInt32(0), rows.GetString(1));
    }
}
