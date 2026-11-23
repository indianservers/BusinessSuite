using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record PmsMilestoneList(DataTable Rows, bool CanCreate, bool CanEdit, bool CanDecide, DataTable Owners);
internal sealed record PmsMilestoneDraft(string Name, string? Description, string Status, DateTime? Start,
    DateTime? Due, int Progress, int? Owner = null);

internal sealed partial class PmsProjectRepository
{
    private const string MilestoneProject = ProjectJoins + " WHERE " + ProjectAccess
        + " AND p.id=@project AND p.deleted_at IS NULL AND NOT p.is_task_collection";
    private const string MilestoneBranch = @"(@branch IS NULL OR EXISTS (
        SELECT 1 FROM public.suite_branch_ownership o WHERE o.resource_table='pms_milestones'
          AND o.resource_key=m.id::text AND o.company_id=@organization AND o.branch_id=@branch))";
    private const string MilestoneApprove = @"
        (p.workspace_id IS NOT NULL AND (@admin OR wm.role IN ('Owner','Admin')))
        OR (p.workspace_id IS NULL AND (@global_approve OR p.manager_user_id=@actor
            OR pm.role IN ('Admin','Project Admin','Manager','Project Manager','Lead','Client','Client Viewer')))";

    internal async Task<PmsMilestoneList> ListMilestonesAsync(int project, CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await GetWorkspaceActorAsync(db,tx,false,cancellation);
        var access = await ReadProjectActionAccessAsync(db,tx,actor,project,false,cancellation);
        using var query = new NpgsqlCommand(@"
            SELECT m.id,m.name,m.description,m.status,m.start_date::timestamp,m.due_date::timestamp,
                coalesce(m.progress_percent,0) AS progress,m.client_approval_status,m.completed_at,
                m.owner_user_id, m.client_rejected_reason,
                m.xmin::text AS revision
            FROM public.pms_milestones m WHERE m.project_id=@project AND " + MilestoneBranch + @"
            ORDER BY m.due_date NULLS LAST,lower(m.name),m.id",db,tx);
        SetBranch(query);
        query.Parameters.AddWithValue("project",project);
        var rows = await ReadTableAsync(query,cancellation);
        var canCreate = access.Manage && actor.ModuleCanCreate;
        var canEdit = access.Manage && actor.ModuleCanEdit;
        var owners = canCreate || canEdit
            ? await ReadProjectEligibleOwnersAsync(db,tx,actor,project,cancellation) : new DataTable();
        return new PmsMilestoneList(rows,canCreate,canEdit,access.Approve && actor.ModuleCanApprove,owners);
    }

    internal async Task<int> SaveMilestoneAsync(int project, int? milestone, string? revision,
        PmsMilestoneDraft draft, CancellationToken cancellation)
    {
        var name=draft.Name.Trim();
        if (name.Length is < 1 or > 180)
            throw new InvalidOperationException("Enter a milestone name of 1 to 180 characters.");
        if (draft.Description?.Length > 8000)
            throw new InvalidOperationException("Use 8,000 or fewer characters for the description.");
        if (draft.Start > draft.Due)
            throw new InvalidOperationException("Milestone start date must not follow its due date.");
        if (draft.Status is not ("Not Started" or "In Progress" or "On Hold" or "Completed" or "Cancelled"))
            throw new InvalidOperationException("Choose a milestone status.");
        if (draft.Progress is < 0 or > 100 || (draft.Status == "Completed") != (draft.Progress == 100))
            throw new InvalidOperationException("Completed milestones require 100% progress. Other milestones must be below 100%.");

        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await GetWorkspaceActorAsync(db,tx,true,cancellation);
        if (!(milestone.HasValue ? actor.ModuleCanEdit : actor.ModuleCanCreate) ||
            !(await ReadProjectActionAccessAsync(db,tx,actor,project,true,cancellation)).Manage)
            throw new UnauthorizedAccessException("You do not have permission to change milestones in this project.");

        int? previousOwner = null;
        if (milestone.HasValue)
            previousOwner = await LockOpenMilestoneAsync(db,tx,project,milestone.Value,revision!,cancellation);
        if (draft.Owner.HasValue && draft.Owner != previousOwner)
        {
            var people = await ReadProjectEligibleOwnersAsync(db,tx,actor,project,cancellation);
            if (!people.Rows.Cast<DataRow>().Any(row => row.Field<int>("id") == draft.Owner))
                throw new InvalidOperationException("Choose an active eligible project owner.");
        }
        string statement = milestone.HasValue ? @"
            UPDATE public.pms_milestones SET name=@name,description=@description,status=@status,start_date=@start,
                due_date=@due,progress_percent=@progress,owner_user_id=@owner,updated_at=clock_timestamp(),
                completed_at=CASE WHEN @status='Completed' THEN coalesce(completed_at,clock_timestamp()) END
            WHERE id=@milestone RETURNING id" : @"
            INSERT INTO public.pms_milestones(project_id,name,description,status,start_date,due_date,progress_percent,owner_user_id,
                client_approval_status,completed_at)
            VALUES(@project,@name,@description,@status,@start,@due,@progress,@owner,'Not Required',
                CASE WHEN @status='Completed' THEN clock_timestamp() END) RETURNING id";
        using var save=new NpgsqlCommand(statement,db,tx);
        save.Parameters.AddWithValue("project",project);
        save.Parameters.AddWithValue("name",name);
        save.Parameters.AddWithValue("description",NpgsqlDbType.Text,(object?)draft.Description??DBNull.Value);
        save.Parameters.AddWithValue("status",draft.Status);
        save.Parameters.AddWithValue("start",NpgsqlDbType.Date,(object?)draft.Start??DBNull.Value);
        save.Parameters.AddWithValue("due",NpgsqlDbType.Date,(object?)draft.Due??DBNull.Value);
        save.Parameters.AddWithValue("progress",draft.Progress);
        save.Parameters.AddWithValue("owner",NpgsqlDbType.Integer,(object?)draft.Owner??DBNull.Value);
        if (milestone.HasValue) save.Parameters.AddWithValue("milestone",milestone.Value);
        var id=(int)(await save.ExecuteScalarAsync(cancellation))!;
        if (!milestone.HasValue)
            await RecordOwnershipAsync(db,tx,"pms_milestones",id,cancellation);
        await RecordMilestoneActivityAsync(db,tx,actor,project,id,milestone.HasValue?"milestone.updated":"milestone.created",
            (milestone.HasValue?"Updated milestone ":"Created milestone ")+name,cancellation);
        await tx.CommitAsync(cancellation);
        return id;
    }

    internal async Task SubmitMilestoneApprovalAsync(int project,int milestone,string revision,CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await GetWorkspaceActorAsync(db,tx,true,cancellation);
        if (!actor.ModuleCanCreate || !(await ReadProjectActionAccessAsync(db,tx,actor,project,true,cancellation)).Manage)
            throw new UnauthorizedAccessException("You do not have permission to submit milestone approvals.");
        await LockOpenMilestoneAsync(db,tx,project,milestone,revision,cancellation);

        using var submit=new NpgsqlCommand(@"
            UPDATE public.pms_milestones SET client_approval_status='Pending',updated_at=clock_timestamp()
            WHERE id=@milestone;
            INSERT INTO public.pms_client_approvals(project_id,milestone_id,requested_by_user_id,status)
            VALUES(@project,@milestone,@actor,'Pending') RETURNING id",db,tx);
        submit.Parameters.AddWithValue("project",project);
        submit.Parameters.AddWithValue("milestone",milestone);
        submit.Parameters.AddWithValue("actor",actor.UserId);
        var id=(int)(await submit.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(db,tx,"pms_client_approvals",id,cancellation);
        await RecordMilestoneActivityAsync(db,tx,actor,project,milestone,"milestone.approval_submitted",
            "Submitted milestone for client approval",cancellation);
        await tx.CommitAsync(cancellation);
    }

    private async Task<(bool Manage,bool Approve)> ReadProjectActionAccessAsync(NpgsqlConnection db,NpgsqlTransaction tx,
        PmsActor actor,int project,bool locked,CancellationToken cancellation)
    {
        using var access=new NpgsqlCommand("SELECT coalesce((" + TaskEditAccess + "),false), coalesce((" + MilestoneApprove + "),false)"
            + MilestoneProject + (locked?" FOR UPDATE OF p":""),db,tx);
        SetActor(access,actor);
        access.Parameters.AddWithValue("project",project);
        access.Parameters.AddWithValue("global_approve",actor.CanApproveOrganizationProjects);
        using var row=await access.ExecuteReaderAsync(cancellation);
        if (!await row.ReadAsync(cancellation))
            throw new UnauthorizedAccessException("This project is outside your current access.");
        return (row.GetBoolean(0),row.GetBoolean(1));
    }

    private async Task<int?> LockOpenMilestoneAsync(NpgsqlConnection db,NpgsqlTransaction tx,
        int project,int milestone,string revision,CancellationToken cancellation)
    {
        using var lockRow=new NpgsqlCommand(@"
            SELECT coalesce(m.client_approval_status,'Not Required'),m.owner_user_id
            FROM public.pms_milestones m WHERE m.project_id=@project AND m.id=@milestone AND m.xmin::text=@revision
                AND " + MilestoneBranch + " FOR UPDATE OF m",db,tx);
        SetBranch(lockRow);
        lockRow.Parameters.AddWithValue("project",project);
        lockRow.Parameters.AddWithValue("milestone",milestone);
        lockRow.Parameters.AddWithValue("revision",revision);
        using var row=await lockRow.ExecuteReaderAsync(cancellation);
        if (!await row.ReadAsync(cancellation))
            throw new InvalidOperationException("The milestone changed or is unavailable. Refresh before trying again.");
        if (row.GetString(0) is "Pending" or "Approved")
            throw new InvalidOperationException("The client approval workflow controls this pending or approved milestone.");
        return row.IsDBNull(1)?null:row.GetInt32(1);
    }

    private async Task<DataTable> ReadProjectEligibleOwnersAsync(NpgsqlConnection db,NpgsqlTransaction tx,
        PmsActor actor,int project,CancellationToken cancellation)
    {
        using var query=new NpgsqlCommand(@"
            SELECT u.id,coalesce(nullif(person.display_name,''),u.email) AS name
            FROM public.pms_projects p JOIN public.users u ON u.is_active
            LEFT JOIN public.common_people person ON person.user_id=u.id
            LEFT JOIN public.employees e ON e.user_id=u.id AND e.deleted_at IS NULL
            LEFT JOIN public.branches b ON b.id=e.branch_id
            WHERE p.id=@project AND coalesce(person.status,'active')='active'
              AND coalesce(person.organization_id,b.company_id,1)=@organization
              AND NOT EXISTS (SELECT 1 FROM public.suite_access_memberships access
                  WHERE access.user_id=u.id AND access.company_id=@organization AND NOT access.active)
              AND (u.id=@actor OR @person_scope IN ('all','company','organization')
                   OR (@person_scope='department' AND e.department_id=@department)
                   OR (@person_scope='branch' AND e.branch_id=@employee_branch))
              AND ((p.workspace_id IS NOT NULL AND EXISTS (
                       SELECT 1 FROM public.pms_workspace_members wm WHERE wm.workspace_id=p.workspace_id
                         AND wm.user_id=u.id AND wm.role IN ('Owner','Admin','Member') AND " + WorkspaceMemberScope + @"))
                   OR (p.workspace_id IS NULL AND EXISTS (
                       SELECT 1 FROM public.pms_project_members pm WHERE pm.project_id=p.id AND pm.user_id=u.id
                         AND pm.role NOT IN ('Client','Client Viewer')
                         AND (@branch IS NULL OR EXISTS (SELECT 1 FROM public.suite_branch_ownership o
                             WHERE o.resource_table='pms_project_members' AND o.company_id=@organization
                               AND o.branch_id=@branch AND o.resource_key=pm.id::text))))
                   OR (p.manager_user_id=u.id AND (@branch IS NULL OR u.id=@actor OR e.branch_id=@branch OR EXISTS (
                       SELECT 1 FROM public.suite_branch_grants g WHERE g.user_id=u.id AND g.company_id=@organization AND g.branch_id=@branch))))
            ORDER BY name,u.id",db,tx);
        SetActor(query,actor);
        query.Parameters.AddWithValue("project",project);
        query.Parameters.AddWithValue("person_scope",actor.PersonScope);
        return await ReadTableAsync(query,cancellation);
    }

    internal async Task DecideMilestoneApprovalAsync(int project,int milestone,string revision,bool approve,string reason,
        CancellationToken cancellation)
    {
        reason=reason.Trim();
        if (!approve && (reason.Length is < 1 or > 8000))
            throw new InvalidOperationException("Enter a reason for rejection up to 8,000 characters.");
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await GetWorkspaceActorAsync(db,tx,true,cancellation);
        if (!actor.ModuleCanApprove || !(await ReadProjectActionAccessAsync(db,tx,actor,project,true,cancellation)).Approve)
            throw new UnauthorizedAccessException("You do not have permission to decide approvals for this project.");

        using var lockRow=new NpgsqlCommand(@"
            SELECT m.id FROM public.pms_milestones m
            WHERE m.project_id=@project AND m.id=@milestone AND m.xmin::text=@revision
              AND m.client_approval_status='Pending' AND " + MilestoneBranch + " FOR UPDATE OF m",db,tx);
        SetBranch(lockRow);
        lockRow.Parameters.AddWithValue("project",project);
        lockRow.Parameters.AddWithValue("milestone",milestone);
        lockRow.Parameters.AddWithValue("revision",revision);
        if (await lockRow.ExecuteScalarAsync(cancellation) is not int)
            throw new InvalidOperationException("The pending milestone changed or is unavailable. Refresh before deciding.");

        string status=approve?"Approved":"Rejected";
        using var decision=new NpgsqlCommand(@"
            UPDATE public.pms_client_approvals a SET status=@status,remarks=@reason,decided_at=clock_timestamp()
            WHERE a.project_id=@project AND a.milestone_id=@milestone AND a.status='Pending'
              AND (@branch IS NULL OR EXISTS (SELECT 1 FROM public.suite_branch_ownership o
                  WHERE o.resource_table='pms_client_approvals' AND o.resource_key=a.id::text
                    AND o.company_id=@organization AND o.branch_id=@branch))",db,tx);
        SetBranch(decision);
        decision.Parameters.AddWithValue("project",project);
        decision.Parameters.AddWithValue("milestone",milestone);
        decision.Parameters.AddWithValue("status",status);
        decision.Parameters.AddWithValue("reason",NpgsqlDbType.Text,approve?DBNull.Value:(object)reason);
        if (await decision.ExecuteNonQueryAsync(cancellation)==0)
            throw new InvalidOperationException("There is no pending approval in this branch for the selected milestone.");

        using var update=new NpgsqlCommand(@"
            UPDATE public.pms_milestones SET client_approval_status=@status,client_rejected_reason=@reason,
                client_approved_at=CASE WHEN @status='Approved' THEN clock_timestamp() END,updated_at=clock_timestamp()
            WHERE id=@milestone",db,tx);
        update.Parameters.AddWithValue("milestone",milestone);
        update.Parameters.AddWithValue("status",status);
        update.Parameters.AddWithValue("reason",NpgsqlDbType.Text,approve?DBNull.Value:(object)reason);
        await update.ExecuteNonQueryAsync(cancellation);
        await RecordMilestoneActivityAsync(db,tx,actor,project,milestone,
            approve?"milestone.approved":"milestone.rejected",
            approve?"Approved milestone":"Rejected milestone",cancellation);
        await tx.CommitAsync(cancellation);
    }

    private async Task RecordMilestoneActivityAsync(NpgsqlConnection db,NpgsqlTransaction tx,PmsActor actor,int project,
        int milestone,string action,string summary,CancellationToken cancellation)
    {
        using var record=new NpgsqlCommand(@"
            INSERT INTO public.pms_activities(project_id,actor_user_id,action,entity_type,entity_id,summary)
            VALUES(@project,@actor,@action,'milestone',@milestone,@summary) RETURNING id",db,tx);
        record.Parameters.AddWithValue("project",project);
        record.Parameters.AddWithValue("actor",actor.UserId);
        record.Parameters.AddWithValue("action",action);
        record.Parameters.AddWithValue("milestone",milestone);
        record.Parameters.AddWithValue("summary",summary);
        var id=(int)(await record.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(db,tx,"pms_activities",id,cancellation);
    }
}


