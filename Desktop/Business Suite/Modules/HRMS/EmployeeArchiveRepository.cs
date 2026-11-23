using Npgsql;

namespace Business_Suite;

internal sealed partial class EmployeeAdministrationRepository
{
    internal async Task ArchiveAsync(int employee, string revision, CancellationToken cancellation)
    {
        using var connection = new NpgsqlConnection(settings.ConnectionString);
        await connection.OpenAsync(cancellation);
        using var transaction = connection.BeginTransaction();
        var actor = await settings.VerifyWriteTargetAsync(connection, transaction, cancellation);
        int branch = settings.BranchId ?? throw new InvalidOperationException("Choose a branch before archiving an employee.");
        var grant = await DesktopModuleAccess.RequireAsync(connection, transaction,
            settings.OrganizationId, branch, actor, "hrms", "delete", "employee_delete");
        if (grant.Scope is not ("organization" or "branch"))
            throw new UnauthorizedAccessException("Archiving employees requires organization or branch employee access.");

        var (status, login, _, _) = await LockEmploymentAsync(connection, transaction, employee, revision, cancellation);
        if (login.HasValue)
            throw new InvalidOperationException("Employee records linked to a login require the employment lifecycle workflow.");

        using var archive = new NpgsqlCommand(@"
            UPDATE public.employees SET status='Terminated', deleted_at=clock_timestamp(),
                deleted_by=@actor, updated_at=clock_timestamp() WHERE id=@employee;
            INSERT INTO public.audit_logs (organization_id,user_id,actor_email,actor_authenticated,method,
                endpoint,status_code,entity_type,entity_id,action,description,old_values,new_values,module)
            SELECT @company,u.id,left(u.email,100),true,'DELETE',@endpoint,200,'employee',@employee,
                'EMPLOYEE_ARCHIVED','Employee archived',json_build_object('status',@status)::text,
                json_build_object('status','Terminated','archived',true)::text,'employees'
            FROM public.users u WHERE u.id=@actor RETURNING id", connection, transaction);
        SetScope(archive);
        archive.Parameters.AddWithValue("actor", actor.Id);
        archive.Parameters.AddWithValue("employee", employee);
        archive.Parameters.AddWithValue("endpoint", $"desktop/employees/{employee}");
        AddText(archive, "status", status);
        int audit = (int)(await archive.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(connection, transaction, "audit_logs", audit, cancellation);
        await transaction.CommitAsync(cancellation);
    }
}
