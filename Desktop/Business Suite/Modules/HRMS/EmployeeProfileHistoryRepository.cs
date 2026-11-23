using System.Data;
using Npgsql;

namespace Business_Suite;

internal sealed partial class EmployeeAdministrationRepository
{
    internal async Task<DataTable> ReadProfileHistoryAsync(int employee, CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        await AuthorizeAsync(db, tx, false, cancellation);
        using (var parent = new NpgsqlCommand("SELECT e.id" + ScopedEmployees + " AND e.id=@employee", db, tx))
        {
            SetScope(parent);
            parent.Parameters.AddWithValue("employee", employee);
            if (await parent.ExecuteScalarAsync(cancellation) is not int)
                throw new InvalidOperationException("The employee profile is unavailable.");
        }

        using var query = new NpgsqlCommand(@"
            WITH history AS (
                SELECT a.id,a.field_name,a.entity_type,a.action,a.created_at,a.actor_user_id,a.old_value_hash,a.new_value_hash,
                    a.old_value_masked,a.new_value_masked,
                    a.is_sensitive OR a.field_name IN ('personal_email','work_email','phone_number','alternate_phone',
                    'emergency_contact_number','present_address','permanent_address','family_information','health_information',
                    'document_url','verification_url','relieving_letter_url','responsibilities','bio',
                    'appointment_letter_url','experience_certificate_url','payslip_url','file_url',
                    'last_drawn_salary','reference_contact','certificate_number','roll_number','registration_number') AS private
                FROM public.field_audit_events a
                WHERE a.employee_id=@employee AND a.module='employee'
                  AND NOT EXISTS (SELECT 1 FROM public.suite_branch_ownership o
                    WHERE o.resource_table='field_audit_events' AND o.resource_key=a.id::text
                    AND (o.company_id<>@company OR o.branch_id<>@branch))
                ORDER BY a.id DESC LIMIT 200
            )
            SELECT id,replace(field_name,'_',' ') AS field_name,replace(entity_type,'_',' ') AS entity_type,
                action,created_at,coalesce(actor_user_id::text,'System') AS actor,
                CASE WHEN private THEN CASE WHEN old_value_hash IS NOT NULL THEN 'Changed (private)' END
                    ELSE old_value_masked END AS before_value,
                CASE WHEN private THEN CASE WHEN new_value_hash IS NOT NULL THEN 'Changed (private)' END
                    ELSE new_value_masked END AS after_value
            FROM history ORDER BY id DESC", db, tx);
        SetScope(query);
        query.Parameters.AddWithValue("employee", employee);
        return await ReadTableAsync(query, cancellation);
    }
}
