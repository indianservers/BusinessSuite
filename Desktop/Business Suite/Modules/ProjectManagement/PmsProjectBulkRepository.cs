using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal enum PmsBulkField { Status, Priority, Deadline, Archive, RestoreArchive, Trash, RestoreTrash }
internal sealed record PmsBulkProject(int Id,string Name,string Revision);
internal sealed record PmsBulkPatch(PmsBulkField Field,string? Value,DateTime? Deadline);
internal sealed record PmsBulkResult(int Saved,List<string> Failures);

internal sealed partial class PmsProjectRepository
{
    internal async Task<List<DataRow>> ReadSelectedExportAsync(int workspaceId,PmsProjectScope scope,IReadOnlyList<int> selected,
        CancellationToken cancellation)
    {
        var rows=await ReadProjectsAsync(workspaceId,scope,selected.ToArray(),cancellation);
        var accessible=rows.Rows.Cast<DataRow>().ToDictionary(row=>row.Field<int>("id"));
        return selected.Distinct().Where(accessible.ContainsKey).Select(id=>accessible[id]).ToList();
    }

    internal async Task<PmsBulkResult> BulkUpdateAsync(IReadOnlyList<PmsBulkProject> projects,PmsBulkPatch patch,
        PmsProjectScope scope,CancellationToken cancellation)
    {
        PmsProjectAction? lifecycle=patch.Field switch
        {
            PmsBulkField.Archive when scope==PmsProjectScope.Active=>PmsProjectAction.Archive,
            PmsBulkField.RestoreArchive when scope==PmsProjectScope.Archived=>PmsProjectAction.Unarchive,
            PmsBulkField.Trash when scope!=PmsProjectScope.Trash=>PmsProjectAction.Trash,
            PmsBulkField.RestoreTrash when scope==PmsProjectScope.Trash=>PmsProjectAction.Restore,
            _=>null
        };
        var assignment=lifecycle.HasValue ? null : patch.Field switch
        {
            PmsBulkField.Status when patch.Value is "Draft" or "Planned" or "Active" or "On Hold" or "Completed" or "Cancelled" =>
                "status=@value, actual_start_date=CASE WHEN @value='Active' THEN coalesce(actual_start_date,current_date) ELSE actual_start_date END,"+
                " actual_end_date=CASE WHEN @value IN ('Completed','Cancelled') THEN coalesce(actual_end_date,current_date) ELSE actual_end_date END",
            PmsBulkField.Priority when patch.Value is "Low" or "Medium" or "High" or "Critical" => "priority=@value",
            PmsBulkField.Deadline when patch.Deadline.HasValue => "due_date=@value",
            _=>throw new InvalidOperationException("Choose a valid project change.")
        };
        if((scope==PmsProjectScope.Trash && !lifecycle.HasValue) || projects.Count==0 ||
            projects.Select(project=>project.Id).Distinct().Count()!=projects.Count)
            throw new InvalidOperationException("Select distinct projects from the current view.");
        using var connection=new NpgsqlConnection(settings.ConnectionString);
        await connection.OpenAsync(cancellation);
        var result=new PmsBulkResult(0,[]);
        foreach(var project in projects)
        {
            cancellation.ThrowIfCancellationRequested();
            try
            {
                using var transaction=connection.BeginTransaction();
                var identity=await settings.VerifyWriteTargetAsync(connection,transaction,cancellation);
                var currentActor=await ResolveActorAsync(settings,identity,connection,transaction,cancellation);
                if(lifecycle!=PmsProjectAction.Restore && !currentActor.ModuleCanEdit)
                    throw new UnauthorizedAccessException("You do not have permission to edit this project.");
                if(lifecycle is PmsProjectAction action)
                {
                    await ApplyProjectLifecycleAsync(connection,transaction,currentActor,project.Id,project.Revision,scope,
                        action,patch.Field==PmsBulkField.RestoreArchive,cancellation);
                    transaction.Commit();
                    result=result with {Saved=result.Saved+1};
                    continue;
                }
                string key=await LockEditableProjectAsync(connection,transaction,currentActor,project.Id,project.Revision,scope,cancellation);
                string column=patch.Field switch {PmsBulkField.Status=>"status",PmsBulkField.Priority=>"priority",_=>"due_date"};
                using var update=new NpgsqlCommand("WITH prior AS (SELECT "+column+" AS value FROM public.pms_projects WHERE id=@id), "+
                    "applied AS (UPDATE public.pms_projects SET "+assignment+", updated_at=now() WHERE id=@id "+
                    (patch.Field==PmsBulkField.Deadline ? "AND (start_date IS NULL OR start_date<=@value) " :
                        "AND (start_date IS NULL OR due_date IS NULL OR start_date<=due_date) ")+
                    "RETURNING "+column+" AS value) SELECT jsonb_build_object('old_values',jsonb_build_object(@field,prior.value),"+
                    "'changed_fields',jsonb_build_object(@field,applied.value))::text, "+
                    "jsonb_build_object('old_value',prior.value,'new_value',applied.value)::text FROM prior CROSS JOIN applied",
                    connection,transaction);
                update.Parameters.AddWithValue("id",project.Id);
                update.Parameters.AddWithValue("field",column);
                if(patch.Field==PmsBulkField.Deadline)
                    update.Parameters.AddWithValue("value",NpgsqlDbType.Date,patch.Deadline!.Value.Date);
                else
                    update.Parameters.AddWithValue("value",patch.Value!);
                string metadata;
                string? statusChange;
                using(var rows=await update.ExecuteReaderAsync(cancellation))
                {
                    if(!await rows.ReadAsync(cancellation))
                        throw new InvalidOperationException("Start date cannot be after the deadline.");
                    metadata=rows.GetString(0);
                    statusChange=patch.Field==PmsBulkField.Status ? rows.GetString(1) : null;
                }
                await RecordActivityAsync(connection,transaction,project.Id,"project.updated","Updated project "+key,metadata,cancellation);
                if(statusChange is not null)
                    await RecordActivityAsync(connection,transaction,project.Id,"project.status_changed",
                        "Changed project status to "+patch.Value,statusChange,cancellation);
                transaction.Commit();
                result=result with {Saved=result.Saved+1};
            }
            catch(Exception error) when(error is InvalidOperationException or UnauthorizedAccessException)
            { result.Failures.Add($"{project.Name}: {error.Message}"); }
            catch(PostgresException)
            { result.Failures.Add($"{project.Name}: PostgreSQL rejected the update."); }
        }
        return result;
    }
}
