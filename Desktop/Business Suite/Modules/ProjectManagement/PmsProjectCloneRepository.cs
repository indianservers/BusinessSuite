using System.Text.Json;
using System.Text.RegularExpressions;
using Npgsql;

namespace Business_Suite;

internal sealed record PmsProjectCloneDraft(string Name, string Key, bool Tasks, bool Dates,
    bool Team, bool Attachments, bool Milestones, bool Dependencies);

internal sealed partial class PmsProjectRepository
{
    internal async Task<int> CloneProjectAsync(int source, string revision, PmsProjectScope scope,
        PmsProjectCloneDraft draft, CancellationToken cancellation)
    {
        var name = draft.Name.Trim();
        var key = draft.Key.Trim().ToUpperInvariant();
        if (name.Length is < 1 or > 180)
            throw new InvalidOperationException("Enter a new project name of 1 to 180 characters.");
        if (!Regex.IsMatch(key, @"\A[A-Z0-9_-]{2,20}\z"))
            throw new InvalidOperationException("Enter a unique project key with 2 to 20 letters, digits, hyphens or underscores.");
        if (scope == PmsProjectScope.Trash)
            throw new InvalidOperationException("Restore the project before duplicating it.");

        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(System.Data.IsolationLevel.RepeatableRead);
        var actor = await ResolveActorAsync(settings,
            await settings.VerifyWriteTargetAsync(db,tx,cancellation),db,tx,cancellation);
        if (!actor.ModuleCanCreate || !actor.ModuleCanEdit)
            throw new UnauthorizedAccessException("Your project permissions do not allow duplication.");
        var sourceKey = await LockEditableProjectAsync(db,tx,actor,source,revision,scope,cancellation);

        using var project = new NpgsqlCommand(@"
            INSERT INTO public.pms_projects(workspace_id,organization_id,client_id,manager_user_id,owner_user_id,
                department_id,branch_id,name,project_key,category,description,status,priority,health,start_date,due_date,
                planned_start_date,planned_end_date,budget_amount,estimated_hours,estimated_cost,billing_status,
                is_client_visible,is_template,is_task_collection,is_archived,progress_percent)
            SELECT workspace_id,coalesce(organization_id,@organization),client_id,coalesce(manager_user_id,@actor),
                coalesce(owner_user_id,manager_user_id,@actor),department_id,branch_id,@name,@key,category,description,
                'Planned',priority,'Good',CASE WHEN @dates THEN start_date END,CASE WHEN @dates THEN due_date END,
                CASE WHEN @dates THEN planned_start_date END,CASE WHEN @dates THEN planned_end_date END,
                budget_amount,estimated_hours,estimated_cost,'Unbilled',is_client_visible,false,false,false,0
            FROM public.pms_projects WHERE id=@source
            ON CONFLICT(organization_id,project_key) DO NOTHING RETURNING id",db,tx);
        project.Parameters.AddWithValue("actor",actor.UserId);
        project.Parameters.AddWithValue("organization",settings.OrganizationId);
        project.Parameters.AddWithValue("source",source);
        project.Parameters.AddWithValue("name",name);
        project.Parameters.AddWithValue("key",key);
        project.Parameters.AddWithValue("dates",draft.Dates);
        if (await project.ExecuteScalarAsync(cancellation) is not int target)
            throw new InvalidOperationException("Project key already exists.");
        await RecordOwnershipAsync(db,tx,"pms_projects",target,cancellation);

        using var children = new NpgsqlCommand(CloneProjectChildren,db,tx);
        SetBranch(children);
        children.Parameters.AddWithValue("actor",actor.UserId);
        children.Parameters.AddWithValue("source",source);
        children.Parameters.AddWithValue("target",target);
        children.Parameters.AddWithValue("source_key",sourceKey);
        children.Parameters.AddWithValue("new_key",key);
        children.Parameters.AddWithValue("dates",draft.Dates);
        children.Parameters.AddWithValue("tasks",draft.Tasks);
        children.Parameters.AddWithValue("milestones",draft.Milestones);
        children.Parameters.AddWithValue("dependencies",draft.Dependencies);
        children.Parameters.AddWithValue("team",draft.Team);
        children.Parameters.AddWithValue("attachments",draft.Attachments);
        await children.ExecuteNonQueryAsync(cancellation);

        await RecordActivityAsync(db,tx,target,"project.cloned",$"Cloned project {sourceKey} into {key}",
            JsonSerializer.Serialize(new { source_project_id = source }),cancellation);
        await tx.CommitAsync(cancellation);
        return target;
    }

    private const string CloneProjectChildren = @"
        WITH owned AS MATERIALIZED (
            SELECT resource_table,resource_key FROM public.suite_branch_ownership
            WHERE company_id=@organization AND branch_id=@branch
        ), milestone_map AS MATERIALIZED (
            SELECT m.*,nextval(pg_get_serial_sequence('public.pms_milestones','id'))::int AS new_id
            FROM public.pms_milestones m WHERE @milestones AND m.project_id=@source AND
                (@branch IS NULL OR ('pms_milestones',m.id::text) IN (SELECT * FROM owned))
        ), milestones AS (
            INSERT INTO public.pms_milestones(id,project_id,owner_user_id,name,description,status,start_date,due_date,
                progress_percent,client_approval_status)
            SELECT new_id,@target,owner_user_id,name,description,'Not Started',
                CASE WHEN @dates THEN start_date END,CASE WHEN @dates THEN due_date END,0,client_approval_status
            FROM milestone_map RETURNING id
        ), task_map AS MATERIALIZED (
            SELECT t.*,nextval(pg_get_serial_sequence('public.pms_tasks','id'))::int AS new_id,
                   row_number() OVER (ORDER BY (t.parent_task_id IS NOT NULL),t.id) AS ordinal
            FROM public.pms_tasks t WHERE @tasks AND t.project_id=@source AND t.deleted_at IS NULL AND
                (@branch IS NULL OR ('pms_tasks',t.id::text) IN (SELECT * FROM owned))
        ), tasks AS (
            INSERT INTO public.pms_tasks(id,project_id,milestone_id,parent_task_id,assignee_user_id,reporter_user_id,
                title,description,task_key,work_type,status,priority,start_date,due_date,estimated_hours,
                original_estimate_hours,remaining_estimate_hours,story_points,rank,security_level,position,is_client_visible,
                recurrence_rule,recurrence_interval,recurrence_until,development_commits,development_prs,
                development_deployments,development_build,is_blocking)
            SELECT t.new_id,@target,m.id,p.new_id,CASE WHEN @team THEN t.assignee_user_id END,@actor,
                t.title,t.description,CASE WHEN starts_with(t.task_key,@source_key)
                    THEN @new_key || substr(t.task_key,length(@source_key)+1)
                    ELSE @new_key || '-' || t.ordinal END,t.work_type,'To Do',t.priority,
                CASE WHEN @dates THEN t.start_date END,CASE WHEN @dates THEN t.due_date END,t.estimated_hours,
                t.original_estimate_hours,t.remaining_estimate_hours,t.story_points,t.rank,t.security_level,t.position,
                t.is_client_visible,CASE WHEN @dates THEN t.recurrence_rule END,t.recurrence_interval,
                CASE WHEN @dates THEN t.recurrence_until END,0,0,0,'Pending',false
            FROM task_map t LEFT JOIN task_map p ON p.id=t.parent_task_id
            LEFT JOIN milestone_map mm ON mm.id=t.milestone_id LEFT JOIN milestones m ON m.id=mm.new_id
            RETURNING id
        ), checklists AS (
            INSERT INTO public.pms_checklist_items(task_id,title,is_completed,position)
            SELECT target.id,c.title,false,c.position
            FROM public.pms_checklist_items c JOIN task_map source ON source.id=c.task_id JOIN tasks target ON target.id=source.new_id
            WHERE @branch IS NULL OR ('pms_checklist_items',c.id::text) IN (SELECT * FROM owned)
            RETURNING id
        ), dependencies AS (
            INSERT INTO public.pms_task_dependencies(task_id,depends_on_task_id,dependency_type,lag_days)
            SELECT left_task.id,right_task.id,d.dependency_type,d.lag_days
            FROM public.pms_task_dependencies d JOIN task_map l ON l.id=d.task_id JOIN tasks left_task ON left_task.id=l.new_id
            JOIN task_map r ON r.id=d.depends_on_task_id JOIN tasks right_task ON right_task.id=r.new_id
            WHERE @dependencies AND (@branch IS NULL OR ('pms_task_dependencies',d.id::text) IN (SELECT * FROM owned))
            RETURNING id
        ), assignees AS (
            INSERT INTO public.pms_task_assignees(task_id,user_id)
            SELECT target.id,a.user_id
            FROM task_map source JOIN tasks target ON target.id=source.new_id
            JOIN LATERAL (
                SELECT old.user_id FROM public.pms_task_assignees old WHERE old.task_id=source.id AND
                    (@branch IS NULL OR ('pms_task_assignees',
                        concat(length(old.task_id::text),':',old.task_id,':',length(old.user_id::text),':',old.user_id))
                        IN (SELECT * FROM owned))
                UNION SELECT source.assignee_user_id WHERE source.assignee_user_id IS NOT NULL
            ) a ON true WHERE @team RETURNING task_id,user_id
        ), team_source AS MATERIALIZED (
            SELECT user_id,role,allocation_percent FROM public.pms_project_members p WHERE @team AND p.project_id=@source
                AND (@branch IS NULL OR ('pms_project_members',p.id::text) IN (SELECT * FROM owned))
        ), team AS (
            INSERT INTO public.pms_project_members(project_id,user_id,role,allocation_percent)
            SELECT @target,t.user_id,t.role,t.allocation_percent FROM team_source t
            UNION ALL SELECT @target,@actor,'Project Manager',100 WHERE NOT EXISTS (SELECT 1 FROM team_source WHERE user_id=@actor)
            RETURNING id
        ), field_map AS MATERIALIZED (
            SELECT f.*,nextval(pg_get_serial_sequence('public.pms_custom_fields','id'))::int AS new_id
            FROM public.pms_custom_fields f WHERE f.project_id=@source AND
                (@branch IS NULL OR ('pms_custom_fields',f.id::text) IN (SELECT * FROM owned))
        ), definitions AS (
            INSERT INTO public.pms_custom_fields(id,project_id,organization_id,scope_key,entity_type,archived,name,task_type,field_type,options_json)
            SELECT new_id,@target,organization_id,'project:' || @target,entity_type,archived,name,task_type,field_type,options_json
            FROM field_map RETURNING id
        ), all_fields AS (
            SELECT f.id AS old_id,d.id AS new_id FROM field_map f JOIN definitions d ON d.id=f.new_id
            UNION ALL SELECT f.id,f.id FROM public.pms_custom_fields f
                WHERE f.project_id IS NULL AND f.organization_id=@organization
        ), project_values AS (
            INSERT INTO public.pms_project_custom_field_values(field_id,project_id,value_json)
            SELECT f.new_id,@target,v.value_json FROM public.pms_project_custom_field_values v
            JOIN all_fields f ON f.old_id=v.field_id
            WHERE v.project_id=@source AND (@branch IS NULL OR ('pms_project_custom_field_values',
                concat(length(v.field_id::text),':',v.field_id,':',length(v.project_id::text),':',v.project_id)) IN (SELECT * FROM owned))
            RETURNING field_id,project_id
        ), task_values AS (
            INSERT INTO public.pms_custom_field_values(field_id,task_id,value_json)
            SELECT f.new_id,copy.id,v.value_json FROM public.pms_custom_field_values v JOIN all_fields f ON f.old_id=v.field_id
            JOIN task_map original ON original.id=v.task_id JOIN tasks copy ON copy.id=original.new_id
            WHERE @branch IS NULL OR ('pms_custom_field_values',
                concat(length(v.field_id::text),':',v.field_id,':',length(v.task_id::text),':',v.task_id)) IN (SELECT * FROM owned)
            RETURNING field_id,task_id
        ), files AS (
            INSERT INTO public.pms_file_assets(uploaded_by_user_id,project_id,task_id,file_name,original_name,mime_type,
                size_bytes,storage_path,version_number,visibility)
            SELECT @actor,@target,copy.id,a.file_name,a.original_name,a.mime_type,a.size_bytes,a.storage_path,1,a.visibility
            FROM public.pms_file_assets a LEFT JOIN task_map original ON original.id=a.task_id
            LEFT JOIN tasks copy ON copy.id=original.new_id
            WHERE @attachments AND a.project_id=@source AND a.deleted_at IS NULL AND (a.task_id IS NULL OR copy.id IS NOT NULL)
                AND (@branch IS NULL OR ('pms_file_assets',a.id::text) IN (SELECT * FROM owned))
            RETURNING id
        ), records AS (
            SELECT 'pms_milestones'::text AS resource_table,id::text AS resource_key FROM milestones
            UNION ALL SELECT 'pms_tasks',id::text FROM tasks
            UNION ALL SELECT 'pms_checklist_items',id::text FROM checklists
            UNION ALL SELECT 'pms_task_dependencies',id::text FROM dependencies
            UNION ALL SELECT 'pms_project_members',id::text FROM team
            UNION ALL SELECT 'pms_custom_fields',id::text FROM definitions
            UNION ALL SELECT 'pms_file_assets',id::text FROM files
            UNION ALL SELECT 'pms_task_assignees',concat(length(task_id::text),':',task_id,':',length(user_id::text),':',user_id) FROM assignees
            UNION ALL SELECT 'pms_project_custom_field_values',
                concat(length(field_id::text),':',field_id,':',length(project_id::text),':',project_id) FROM project_values
            UNION ALL SELECT 'pms_custom_field_values',
                concat(length(field_id::text),':',field_id,':',length(task_id::text),':',task_id) FROM task_values
        )
        INSERT INTO public.suite_branch_ownership(resource_table,resource_key,company_id,branch_id,source)
        SELECT resource_table,resource_key,@organization,@branch,'validated-write' FROM records WHERE @branch IS NOT NULL";
}

