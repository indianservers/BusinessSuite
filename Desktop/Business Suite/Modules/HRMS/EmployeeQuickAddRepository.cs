using System.Data;
using System.Net.Mail;
using System.Security.Cryptography;
using System.Text;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record EmployeeQuickAddDraft(string FirstName, string? LastName, DateTime Joining,
    int? Department, string? Email, string EmploymentType);

internal sealed partial class EmployeeAdministrationRepository
{
    private const string CreateDepartmentScope = @" FROM public.departments d
        WHERE d.branch_id=@branch AND (d.organization_id IS NULL OR d.organization_id=@company) AND d.is_active
          AND NOT EXISTS (SELECT 1 FROM public.suite_branch_ownership o
            WHERE o.resource_table='departments' AND o.resource_key=d.id::text AND (o.company_id<>@company OR o.branch_id<>@branch))";

    internal async Task<DataTable> ReadCreateDepartmentsAsync(CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        await RequireCreateEmployeeAsync(db, tx, false, cancellation);
        using var query = new NpgsqlCommand("SELECT d.id,d.name" + CreateDepartmentScope + " ORDER BY d.name,d.id", db, tx);
        SetScope(query);
        return await ReadTableAsync(query, cancellation);
    }

    internal async Task<(int Id, string Code)> QuickAddAsync(EmployeeQuickAddDraft draft, CancellationToken cancellation)
    {
        var firstName = Clean(draft.FirstName, 80);
        var lastName = Clean(draft.LastName, 80) ?? "";
        var email = Clean(draft.Email, 150)?.ToLowerInvariant();
        if (firstName is null)
            throw new InvalidOperationException("Enter a first name.");
        if (email is not null)
        {
            try
            {
                var address = new MailAddress(email);
                if (address.Address != email || !address.Host.Contains("."))
                    throw new FormatException();
            }
            catch (FormatException) { throw new InvalidOperationException("Enter a valid personal email address."); }
        }
        string employment = draft.EmploymentType switch
        {
            "Full-time" => "full_time", "Part-time" => "part_time", "Intern" => "intern", "Contract" => "contract",
            _ => throw new InvalidOperationException("Choose an employment type.")
        };

        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await RequireCreateEmployeeAsync(db, tx, true, cancellation);
        if (draft.Department.HasValue)
        {
            using var department = new NpgsqlCommand("SELECT d.id" + CreateDepartmentScope + " AND d.id=@id FOR SHARE OF d", db, tx);
            SetScope(department);
            department.Parameters.AddWithValue("id", draft.Department.Value);
            if (await department.ExecuteScalarAsync(cancellation) is not int)
                throw new InvalidOperationException("Choose an active department in the selected branch.");
        }

        using (var fields = new NpgsqlCommand(@"
            SELECT EXISTS (SELECT 1 FROM public.custom_field_definitions f
                WHERE f.module IN ('employees','employee') AND f.is_active AND f.is_required
                AND NOT EXISTS (SELECT 1 FROM public.suite_branch_ownership o
                    WHERE o.resource_table='custom_field_definitions' AND o.resource_key=f.id::text
                      AND o.company_id<>@company))", db, tx))
        {
            SetScope(fields);
            if (await fields.ExecuteScalarAsync(cancellation) is true)
                throw new InvalidOperationException("Required employee custom fields must be completed in the full employee creation workflow.");
        }

        if (email is not null)
        {
            using var hash = SHA256.Create();
            byte[] digest = hash.ComputeHash(Encoding.UTF8.GetBytes("employee-contact:" + email));
            ulong key = 0;
            for (int index = 0; index < 8; index++)
                key = (key << 8) | digest[index];
            using var emailLock = new NpgsqlCommand("SELECT pg_advisory_xact_lock(@key)", db, tx);
            emailLock.Parameters.AddWithValue("key", unchecked((long)key));
            await emailLock.ExecuteNonQueryAsync(cancellation);
            using var duplicate = new NpgsqlCommand(@"
                SELECT EXISTS (SELECT 1 FROM public.employees e LEFT JOIN public.users u ON u.id=e.user_id
                    WHERE e.deleted_at IS NULL AND (lower(trim(e.personal_email))=@email
                        OR lower(trim(e.work_email))=@email OR lower(trim(u.email))=@email))", db, tx);
            duplicate.Parameters.AddWithValue("email", email);
            if (await duplicate.ExecuteScalarAsync(cancellation) is true)
                throw new InvalidOperationException("A likely matching employee already exists. Review the existing record before saving.");
        }

        actor = await RequireCreateEmployeeAsync(db, tx, true, cancellation);
        string code = "EMP" + Guid.NewGuid().ToString("N").Substring(0, 12).ToUpperInvariant();
        using var insert = new NpgsqlCommand(@"
            INSERT INTO public.employees(employee_id,first_name,last_name,branch_id,department_id,date_of_joining,
                personal_email,employment_type,worker_type,status,work_location,probation_period_months,timezone,
                account_type,salary_currency,directory_visibility,profile_completeness,created_at,updated_at)
            VALUES(@code,@first,@last,@branch,@department,@joining,@email,@employment,'Employee','Active',
                'Office',6,'Asia/Kolkata','Savings','INR','public',0,clock_timestamp(),clock_timestamp())
            RETURNING id", db, tx);
        SetScope(insert);
        insert.Parameters.AddWithValue("code", code);
        insert.Parameters.AddWithValue("first", firstName);
        insert.Parameters.AddWithValue("last", lastName);
        AddText(insert, "email", email);
        insert.Parameters.AddWithValue("employment", draft.EmploymentType);
        insert.Parameters.Add("department", NpgsqlDbType.Integer).Value = (object?)draft.Department ?? DBNull.Value;
        insert.Parameters.AddWithValue("joining", NpgsqlDbType.Date, draft.Joining.Date);
        int id = (int)(await insert.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(db, tx, "employees", id, cancellation);
        await CreateEmployeeOnboardingAsync(db, tx, id, draft.Joining.Date, employment, actor.Id, cancellation);

        using var audit = new NpgsqlCommand(@"
            INSERT INTO public.audit_logs(organization_id,user_id,actor_email,actor_authenticated,method,endpoint,status_code,
                entity_type,entity_id,action,description,new_values,module)
            SELECT @company,id,left(email,100),true,'POST','desktop/employees/workbench/quick-add',201,'employee',@employee,
                'QUICK_ADD_EMPLOYEE','Minimal employee profile created','{""linked_user_id"":null}','employees'
            FROM public.users WHERE id=@actor RETURNING id", db, tx);
        SetScope(audit);
        audit.Parameters.AddWithValue("actor", actor.Id);
        audit.Parameters.AddWithValue("employee", id);
        int auditId = (int)(await audit.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(db, tx, "audit_logs", auditId, cancellation);
        await tx.CommitAsync(cancellation);
        return (id, code);
    }

    private async Task<DesktopActor> RequireCreateEmployeeAsync(NpgsqlConnection db, NpgsqlTransaction tx, bool write,
        CancellationToken cancellation)
    {
        int branch = settings.BranchId ?? throw new InvalidOperationException("Choose a branch before adding an employee.");
        var actor = write ? await settings.VerifyWriteTargetAsync(db, tx, cancellation)
            : await settings.RequireActorAsync(db, tx, cancellation);
        var grant = await DesktopModuleAccess.RequireAsync(db, tx, settings.OrganizationId, branch, actor,
            "hrms", "create", "employee_create");
        if (!actor.CanWriteBranch || grant.Scope is not ("organization" or "branch"))
            throw new UnauthorizedAccessException("Adding employees requires write access in the selected branch.");
        return actor;
    }

    private async Task<int?> CreateEmployeeOnboardingAsync(NpgsqlConnection db, NpgsqlTransaction tx, int employee, DateTime joining,
        string employment, int actor, CancellationToken cancellation, int? selectedTemplate = null)
    {
        using var create = new NpgsqlCommand(@"
            WITH template AS (
                SELECT t.id FROM public.onboarding_templates t
                WHERE t.is_active AND ((@template IS NULL AND t.applicable_for IN ('all',@employment)) OR t.id=@template)
                  AND (t.organization_id=@company OR t.organization_id IS NULL)
                  AND NOT EXISTS (SELECT 1 FROM public.suite_branch_ownership o
                    WHERE o.resource_table='onboarding_templates' AND o.resource_key=t.id::text
                      AND (o.company_id<>@company OR o.branch_id<>@branch))
                ORDER BY (t.applicable_for=@employment) DESC,t.created_at,t.id LIMIT 1
            ), task_source AS (
                SELECT r.*,greatest(coalesce(r.due_day_offset,1)-1,0) AS day_offset
                FROM public.onboarding_template_tasks r JOIN template t ON t.id=r.template_id
                WHERE NOT EXISTS (SELECT 1 FROM public.suite_branch_ownership o
                    WHERE o.resource_table='onboarding_template_tasks' AND o.resource_key=r.id::text
                      AND (o.company_id<>@company OR o.branch_id<>@branch))
            ), onboard AS (
                INSERT INTO public.employee_onboardings(employee_id,template_id,start_date,target_completion_date,status,
                    completion_percentage,created_by)
                SELECT @employee,t.id,@joining,@joining+coalesce((SELECT max(day_offset) FROM task_source),0),
                    CASE WHEN EXISTS(SELECT 1 FROM task_source WHERE @joining+day_offset <
                        (clock_timestamp() AT TIME ZONE coalesce(nullif((SELECT default_timezone FROM public.companies
                            WHERE id=@company),''),'Asia/Kolkata'))::date) THEN 'overdue' ELSE 'not_started' END,0,@actor
                FROM template t RETURNING id
            ), tasks AS (
                INSERT INTO public.employee_onboarding_tasks(employee_onboarding_id,template_task_id,task_name,category,due_date,status,assigned_to_user_id)
                SELECT o.id,r.id,r.task_name,r.category,@joining+r.day_offset,'pending',
                    CASE lower(trim(coalesce(r.assigned_to_role,'employee')))
                     WHEN 'employee' THEN e.user_id WHEN 'manager' THEN manager.user_id END
                FROM onboard o CROSS JOIN task_source r JOIN public.employees e ON e.id=@employee
                LEFT JOIN public.employees manager ON manager.id=e.reporting_manager_id AND manager.branch_id=@branch
                    AND manager.deleted_at IS NULL
                ORDER BY coalesce(r.order_index,0),r.id RETURNING id
            )
            , owned AS (
                INSERT INTO public.suite_branch_ownership(resource_table,resource_key,company_id,branch_id,source)
                SELECT 'employee_onboardings',id::text,@company,@branch,'validated-write' FROM onboard
                UNION ALL SELECT 'employee_onboarding_tasks',id::text,@company,@branch,'validated-write' FROM tasks
            )
            SELECT id FROM onboard", db, tx);
        SetScope(create);
        create.Parameters.AddWithValue("employee", employee);
        create.Parameters.AddWithValue("joining", NpgsqlDbType.Date, joining);
        create.Parameters.AddWithValue("employment", employment);
        create.Parameters.AddWithValue("actor", actor);
        create.Parameters.Add("template", NpgsqlDbType.Integer).Value = (object?)selectedTemplate ?? DBNull.Value;
        return await create.ExecuteScalarAsync(cancellation) is int id ? id : (int?)null;
    }
}
