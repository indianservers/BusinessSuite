using System.Data;
using Npgsql;

namespace Business_Suite;

internal sealed partial class EmployeeAdministrationRepository
{
    internal async Task<DataTable> ReadProfileChecksAsync(int employee, int days, CancellationToken cancellation)
    {
        if (days is < 1 or > 90)
            throw new InvalidOperationException("Choose a reminder window from 1 to 90 days.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await AuthorizeAsync(db, tx, false, cancellation);
        bool ownProfile;
        using (var parent = new NpgsqlCommand("SELECT coalesce(e.user_id=@actor,false)" + ScopedEmployees + " AND e.id=@employee", db, tx))
        {
            SetScope(parent);
            parent.Parameters.AddWithValue("employee", employee);
            parent.Parameters.AddWithValue("actor", actor.Id);
            if (await parent.ExecuteScalarAsync(cancellation) is not bool self)
                throw new InvalidOperationException("The employee profile is unavailable.");
            ownProfile = self;
        }

        bool documents = await CanReadEmployeeDocumentsAsync(db, tx, actor, ownProfile);

        using var query = new NpgsqlCommand(@"
            WITH today AS (
                SELECT (clock_timestamp() AT TIME ZONE coalesce(nullif(default_timezone,''),'Asia/Kolkata'))::date AS day
                FROM public.companies WHERE id=@company
            ), outside AS (
                SELECT resource_table,resource_key FROM public.suite_branch_ownership
                WHERE (company_id<>@company OR branch_id<>@branch) AND resource_table IN ('employee_certifications',
                    'employee_documents','employee_onboardings','employee_onboarding_tasks','employee_lifecycle_events','employee_change_requests')
            ), checks AS (
                SELECT 1 AS seq,'Certification expiry' AS category,c.certification_name AS name,
                    CASE WHEN c.expiry_date<t.day THEN 'Expired' WHEN c.expiry_date=t.day THEN 'Expires today'
                         WHEN c.expiry_date<=t.day+30 THEN 'Due within 30 days'
                         WHEN c.expiry_date<=t.day+60 THEN 'Due within 60 days' ELSE 'Due within 90 days' END AS status,
                    c.expiry_date AS due_date
                FROM public.employee_certifications c CROSS JOIN today t
                WHERE c.employee_id=@employee AND c.expiry_date<=t.day+@days AND NOT EXISTS (
                    SELECT 1 FROM outside x WHERE x.resource_table='employee_certifications' AND x.resource_key=c.id::text)
                UNION ALL
                SELECT 2,'Document',coalesce(nullif(d.document_name,''),d.document_type),
                    coalesce(nullif(d.verification_status,''),CASE WHEN d.is_verified THEN 'Verified' ELSE 'Pending' END)
                    || CASE WHEN d.expiry_date<t.day THEN ' · Expired' ELSE '' END,d.expiry_date
                FROM public.employee_documents d CROSS JOIN today t
                WHERE @documents AND d.employee_id=@employee AND NOT EXISTS (
                    SELECT 1 FROM outside x WHERE x.resource_table='employee_documents' AND x.resource_key=d.id::text)
                UNION ALL
                SELECT 3,'Onboarding',a.task_name,'Required',a.due_date
                FROM public.employee_onboardings o JOIN public.employee_onboarding_tasks a ON a.employee_onboarding_id=o.id
                JOIN public.onboarding_template_tasks r ON r.id=a.template_task_id
                WHERE o.employee_id=@employee AND o.status NOT IN ('cancelled','completed') AND a.status<>'completed' AND r.is_mandatory
                    AND NOT EXISTS (SELECT 1 FROM outside x WHERE x.resource_table='employee_onboardings' AND x.resource_key=o.id::text)
                    AND NOT EXISTS (SELECT 1 FROM outside x WHERE x.resource_table='employee_onboarding_tasks' AND x.resource_key=a.id::text)
                UNION ALL
                SELECT 4,'Profile change requests',count(*)::text || ' pending','Pending',NULL
                FROM public.employee_change_requests r
                WHERE r.employee_id=@employee AND r.status='Pending' AND (r.organization_id IS NULL OR r.organization_id=@company)
                  AND NOT EXISTS (SELECT 1 FROM outside x WHERE x.resource_table='employee_change_requests' AND x.resource_key=r.id::text)
                UNION ALL
                SELECT 5,'Scheduled transfer','Transfer #' || l.id,
                    CASE WHEN l.effective_from<=t.day THEN 'Ready to apply' ELSE 'Scheduled' END,l.effective_from
                FROM public.employee_lifecycle_events l CROSS JOIN today t
                WHERE l.employee_id=@employee AND l.event_type='Scheduled transfer' AND NOT EXISTS (
                    SELECT 1 FROM outside x WHERE x.resource_table='employee_lifecycle_events' AND x.resource_key=l.id::text)
            )
            SELECT category,name,status,due_date::timestamp AS due_date FROM checks ORDER BY seq,due_date NULLS LAST,name", db, tx);
        SetScope(query);
        query.Parameters.AddWithValue("employee", employee);
        query.Parameters.AddWithValue("days", days);
        query.Parameters.AddWithValue("documents", documents);
        return await ReadTableAsync(query, cancellation);
    }
}
