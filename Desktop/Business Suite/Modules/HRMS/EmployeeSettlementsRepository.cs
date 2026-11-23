using System.Data;
using Npgsql;

namespace Business_Suite;

internal sealed record EmployeeSettlementsView(DataTable Settlements, DataTable Components, bool CanRun, bool CanApprove,
    bool CanGenerate, EmployeeSettlementClearance Clearance);

internal sealed record EmployeeSettlementClearance(int Completed, int Total, bool Available);

internal sealed record EmployeeSettlementComponent(string Type, string Name, decimal Amount, string Source, bool Manual, string Remarks);

internal sealed partial class EmployeeAdministrationRepository
{
    private const string SettlementExitScope = @"(s.exit_record_id IS NULL OR EXISTS(
        SELECT 1 FROM public.exit_records x WHERE x.id=s.exit_record_id AND x.employee_id=s.employee_id AND " + ExitOwnership + @"))
        AND NOT EXISTS (SELECT 1 FROM public.suite_branch_ownership owner WHERE owner.resource_table='full_final_settlements'
            AND owner.resource_key=s.id::text AND (owner.company_id<>@company OR owner.branch_id<>@branch))";

    internal async Task<DataTable> ReadSettlementRegisterAsync(string search, string state, CancellationToken cancellation, bool own = false)
    {
        state=state.Trim().ToLowerInvariant().Replace(' ','_');
        if (state is not ("all" or "draft" or "pending_approval" or "approved" or "rejected" or "paid" or "cancelled"))
            throw new InvalidOperationException("Choose a settlement status.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await settings.RequireActorAsync(db, tx, cancellation);
        if (!own)
            await RequireSettlementGrantAsync(db, tx, actor, "view", "payroll_view", "payroll_run");
        else if (settings.BranchId is null)
            throw new InvalidOperationException("Choose a branch to view settlement statements.");

        using var query = new NpgsqlCommand(@"
            WITH employees_in_scope AS (
                SELECT e.id,e.employee_id,e.user_id,concat_ws(' ',e.first_name,e.last_name) AS employee_name " + ScopedEmployees + @"
            )
            SELECT s.id,e.id AS employee,s.exit_record_id AS exit,e.employee_id,e.employee_name,
                coalesce(s.last_working_date,s.settlement_date)::timestamp AS last_working_date,
                s.settlement_date::timestamp,s.net_payable,n.status
            FROM public.full_final_settlements s
            JOIN employees_in_scope e ON e.id=s.employee_id
            CROSS JOIN LATERAL (SELECT replace(lower(btrim(coalesce(s.status,'draft'))),' ','_') AS status) n
            WHERE s.organization_id=@company AND " + SettlementExitScope + @"
                AND (NOT @own OR (e.user_id=@actor AND n.status IN ('approved','paid')))
                AND (@state='all' OR @state=n.status)
                AND (@search='' OR strpos(lower(e.employee_id),lower(@search))>0
                    OR strpos(lower(e.employee_name),lower(@search))>0)
            ORDER BY s.created_at DESC NULLS LAST,s.id DESC",db,tx);
        SetScope(query);
        query.Parameters.AddWithValue("search",search.Trim());
        query.Parameters.AddWithValue("state",state);
        query.Parameters.AddWithValue("own",own);
        query.Parameters.AddWithValue("actor",actor.Id);
        return await ReadTableAsync(query,cancellation);
    }

    internal async Task<EmployeeSettlementsView> ReadSettlementsAsync(int employee, int? record, CancellationToken cancellation, bool own = false)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await settings.RequireActorAsync(db, tx, cancellation);
        if (!own)
            await RequireSettlementGrantAsync(db, tx, actor, "view", "payroll_view", "payroll_run");
        else if (settings.BranchId is null)
            throw new InvalidOperationException("Choose a branch to view settlement statements.");
        var person = await ReadExitEmployeeAsync(db, tx, employee, false, cancellation);
        if (own && person.Login != actor.Id)
            throw new UnauthorizedAccessException("This settlement statement is available only to the employee.");
        const string released = " AND replace(lower(btrim(s.status)),' ','_') IN ('approved','paid')";
        using var header = SettlementQuery(@"SELECT s.id,s.xmin::text AS revision,replace(lower(btrim(coalesce(s.status,'draft'))),' ','_') AS status,
            s.settlement_date::timestamp,s.last_working_date::timestamp,s.net_payable,s.remarks,
            s.submitted_at,s.approved_at,s.rejected_at,s.paid_at,
            (SELECT name FROM public.companies WHERE id=s.organization_id) AS company_name,
            (SELECT employee_id FROM public.employees WHERE id=s.employee_id) AS employee_code,
            (SELECT concat_ws(' ',first_name,last_name) FROM public.employees WHERE id=s.employee_id) AS employee_name
            FROM public.full_final_settlements s WHERE ", (own ? released : "") + " ORDER BY s.settlement_date DESC,s.id DESC",
            db, tx, employee, record);
        using var lines = SettlementQuery(@"SELECT l.settlement_id,CASE WHEN lower(l.line_type) IN ('deduction','recovery') THEN 'deduction' ELSE 'earning' END AS line_type,
            l.component_name,l.amount,l.source,l.remarks,coalesce(l.is_manual_adjustment,false) AS is_manual_adjustment
            FROM public.full_final_settlement_lines l JOIN public.full_final_settlements s ON s.id=l.settlement_id
            WHERE ", (own ? released : "") + " ORDER BY l.id", db, tx, employee, record);
        var rows = await ReadTableAsync(header, cancellation);
        var components = await ReadTableAsync(lines, cancellation);
        bool canRun = !own && actor.CanWriteBranch && await CanChangeSettlementAsync(db, tx, actor,"payroll_run");
        bool canApprove = !own && actor.CanWriteBranch && await CanChangeSettlementAsync(db, tx, actor,"payroll_approve");
        bool canGenerate = !own && record.HasValue && actor.CanWriteBranch && rows.Rows.Count == 0 &&
            await CanChangeSettlementAsync(db, tx, actor,"payroll_run","payroll_view");
        var clearance = record is int exit
            ? await ReadSettlementClearanceAsync(db,tx,employee,exit,cancellation)
            : new EmployeeSettlementClearance(0,0,true);
        return new(rows,components,canRun,canApprove,canGenerate,clearance);
    }

    private async Task<EmployeeSettlementClearance> ReadSettlementClearanceAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        int employee, int record, CancellationToken cancellation)
    {
        using var query = new NpgsqlCommand(@"
            SELECT count(i.id)::int,
                (count(i.id) FILTER (WHERE " + ExitItemOwnership + @"))::int,
                (count(i.id) FILTER (WHERE coalesce(i.is_completed,false) AND " + ExitItemOwnership + @"))::int
            FROM public.exit_records x LEFT JOIN public.exit_checklist_items i ON i.exit_record_id=x.id
            WHERE x.id=@exit AND x.employee_id=@employee AND " + ExitOwnership + " GROUP BY x.id",db,tx);
        SetScope(query);
        query.Parameters.AddWithValue("exit",record);
        query.Parameters.AddWithValue("employee",employee);
        try
        {
            using var row = await query.ExecuteReaderAsync(cancellation);
            if (await row.ReadAsync(cancellation) && row.GetInt32(0) == row.GetInt32(1))
                return new(row.GetInt32(2),row.GetInt32(1),true);
        }
        catch (PostgresException ex) when (ex.SqlState == PostgresErrorCodes.InsufficientPrivilege) { }
        return new(0,0,false);
    }

    internal async Task<DataTable> ReadSettlementCandidatesAsync(string search, CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await settings.RequireActorAsync(db,tx,cancellation);
        await RequireSettlementGrantAsync(db,tx,actor,"edit","payroll_run","payroll_view");
        using var query = new NpgsqlCommand(@"SELECT e.id,e.employee_id || ' · ' || concat_ws(' ',e.first_name,e.last_name) AS label"
            + ScopedEmployees + @" AND (@search='' OR strpos(lower(e.employee_id),lower(@search))>0
                    OR strpos(lower(concat_ws(' ',e.first_name,e.last_name)),lower(@search))>0)
                ORDER BY e.first_name,e.last_name,e.id LIMIT 500",db,tx);
        SetScope(query);
        query.Parameters.AddWithValue("search",search.Trim());
        return await ReadTableAsync(query,cancellation);
    }

    internal async Task<DataTable> ReadSettlementPreparationExitsAsync(int employee,CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await settings.RequireActorAsync(db,tx,cancellation);
        await RequireSettlementGrantAsync(db,tx,actor,"edit","payroll_run","payroll_view");
        await ReadExitEmployeeAsync(db,tx,employee,false,cancellation);
        using var query = new NpgsqlCommand(@"
            SELECT x.id,concat('Exit #',x.id,' · ',to_char(x.last_working_date,'DD Mon YYYY'),' · ',x.status) AS label,
                x.last_working_date::timestamp,x.status
            FROM public.exit_records x WHERE x.employee_id=@employee AND " + ExitOwnership + " ORDER BY x.id DESC",db,tx);
        SetScope(query);
        query.Parameters.AddWithValue("employee",employee);
        return await ReadTableAsync(query,cancellation);
    }

    internal async Task<int> GenerateSettlementAsync(int employee, int record, string remarks, CancellationToken cancellation) =>
        (await GenerateSettlementCoreAsync(employee,record,null,"",remarks,cancellation)).Settlement;

    internal Task<(int Settlement, int Exit)> PrepareStandaloneSettlementAsync(int employee, DateTime date, string reason, string remarks,
        CancellationToken cancellation, int? selectedExit = null) =>
        GenerateSettlementCoreAsync(employee,selectedExit,date.Date,reason,remarks,cancellation);

    private async Task<(int Settlement, int Exit)> GenerateSettlementCoreAsync(int employee, int? requestedExit, DateTime? date, string reason, string remarks,
        CancellationToken cancellation)
    {
        remarks = remarks.Trim();
        reason = reason.Trim();
        if (remarks.Length > 1000 || reason.Length > 1000)
            throw new InvalidOperationException("Use at most 1,000 characters for the reason and remarks.");

        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.Serializable);
        var actor = await settings.VerifyWriteTargetAsync(db, tx, cancellation);
        await RequireSettlementGrantAsync(db, tx, actor, "edit", "payroll_run", "payroll_view");
        var current = await ReadExitEmployeeAsync(db, tx, employee, true, cancellation);
        int record = date is DateTime lastWorkingDate
            ? await PrepareSettlementExitAsync(db,tx,employee,lastWorkingDate,reason,current.Joining,current.Today,requestedExit,cancellation)
            : requestedExit!.Value;

        using var cmd = new NpgsqlCommand(@"
            WITH departure AS (
                SELECT x.last_working_date AS last_day,x.resignation_date AS resigned,x.notice_period_days AS notice,
                    x.notice_waived AS waived,date_trunc('month',x.last_working_date)::date AS month_start,
                    (date_trunc('month',x.last_working_date)+interval '1 month - 1 day')::date AS month_end
                FROM public.exit_records x
                WHERE x.id=@record AND x.employee_id=@employee AND " + ExitOwnership + @"
                  AND x.last_working_date>=@joining AND NOT EXISTS (
                    SELECT 1 FROM public.full_final_settlements s WHERE s.exit_record_id=x.id)
            ), salary AS (
                SELECT d.*,coalesce(CASE WHEN abs(pay.ctc * 100) % 2 = 0.5 THEN trunc(pay.ctc,2) ELSE round(pay.ctc,2) END,0) AS ctc,
                    coalesce(CASE WHEN abs(pay.basic * 100) % 2 = 0.5 THEN trunc(pay.basic,2) ELSE round(pay.basic,2) END,0) AS basic
                FROM departure d CROSS JOIN LATERAL (
                    SELECT sum((coalesce(s.ctc,0)/12) * p.weight) AS ctc,
                           sum(coalesce(nullif(s.basic,0),(coalesce(s.ctc,0)/12)*0.4) * p.weight) AS basic
                    FROM public.employee_salaries s CROSS JOIN LATERAL (
                        SELECT greatest(0,least(coalesce(s.effective_to,d.month_end),d.month_end) -
                            greatest(coalesce(s.effective_date,s.effective_from),d.month_start)+1)::numeric /
                            (d.month_end-d.month_start+1) AS weight
                    ) p
                    WHERE s.employee_id=@employee AND s.effective_from<=d.month_end
                        AND (s.effective_to IS NULL OR s.effective_to>=d.month_start)
                ) pay
            ), rates AS (
                SELECT s.*,round(coalesce(nullif(basic,0),ctc)/30,2) AS daily_basic,
                    greatest(last_day-@joining,0)::numeric / 365 AS years_served
                FROM salary s
            ), amounts AS (
                SELECT r.last_day,round(ctc * extract(day from last_day) / extract(day from month_end),2) AS unpaid,
                    round(daily_basic * greatest(0,(SELECT sum(round(coalesce(b.allocated,0)+coalesce(b.carried_forward,0)
                        -coalesce(b.used,0)-coalesce(b.pending,0),2)) FROM public.leave_balances b
                        JOIN public.leave_types t ON t.id=b.leave_type_id
                        WHERE t.encashable IS TRUE AND b.employee_id=@employee AND b.year=extract(year FROM r.last_day))),2) AS leave,
                    CASE WHEN years_served>=5 THEN round(coalesce(nullif(basic,0),ctc*0.4)*15/26*years_served,2) ELSE 0 END AS gratuity,
                    CASE WHEN coalesce(waived,false) IS FALSE AND resigned IS NOT NULL THEN
                        round(daily_basic*greatest(0,notice-greatest(0,last_day-resigned+1)),2) ELSE 0 END AS notice,
                    coalesce((SELECT sum(round(coalesce(balance_amount,0),2)) FROM public.employee_loans
                        WHERE employee_id=@employee AND status IN ('Active','Approved')),0) AS loan,
                    coalesce((SELECT sum(round(coalesce(amount,0),2)) FROM public.reimbursements
                        WHERE employee_id=@employee AND status='Approved' AND payroll_record_id IS NULL),0) AS reimbursement
                FROM rates r
            ), created AS (
                INSERT INTO public.full_final_settlements(organization_id,employee_id,exit_record_id,settlement_date,
                    last_working_date,status,unpaid_salary,leave_encashment_amount,gratuity_amount,notice_recovery_amount,
                    loan_recovery_amount,reimbursement_payable,bonus_payable,other_earnings,other_deductions,other_payables,
                    other_recoveries,net_payable,prepared_by,remarks)
                SELECT @company,@employee,@record,@today,last_day,'draft',unpaid,leave,gratuity,notice,loan,reimbursement,
                    0,0,0,0,0,unpaid+leave+gratuity+reimbursement-notice-loan,@actor,nullif(@remarks,'') FROM amounts
                RETURNING *
            ), components AS (
                INSERT INTO public.full_final_settlement_lines(settlement_id,line_type,component_name,amount,source,is_manual_adjustment)
                SELECT c.id,l.kind,l.name,l.amount,l.source,false FROM created c CROSS JOIN LATERAL (VALUES
                    ('earning','Unpaid salary',c.unpaid_salary,'payroll'),
                    ('earning','Leave encashment',c.leave_encashment_amount,'leave'),
                    ('earning','Gratuity',c.gratuity_amount,'payroll'),
                    ('earning','Reimbursement payable',c.reimbursement_payable,'payroll'),
                    ('earning','Bonus / variable pay',0,'payroll'),
                    ('deduction','Notice period recovery',c.notice_recovery_amount,'exit'),
                    ('deduction','Loan / advance recovery',c.loan_recovery_amount,'payroll')
                ) l(kind,name,amount,source)
            ) SELECT id FROM created", db, tx);
        SetScope(cmd);
        cmd.Parameters.AddWithValue("employee", employee);
        cmd.Parameters.AddWithValue("record", record);
        cmd.Parameters.AddWithValue("actor", actor.Id);
        cmd.Parameters.AddWithValue("remarks", remarks);
        cmd.Parameters.AddWithValue("today", NpgsqlTypes.NpgsqlDbType.Date, current.Today);
        cmd.Parameters.AddWithValue("joining", NpgsqlTypes.NpgsqlDbType.Date, current.Joining);
        var created = await cmd.ExecuteScalarAsync(cancellation);
        if (created is not int id)
            throw new InvalidOperationException("An exit case with a valid last working date and no existing settlement is required.");
        await RecordExitAuditAsync(db, tx, actor.Id, employee, "SETTLEMENT_GENERATED", "Final settlement draft generated",
            new { settlement_id = id, exit_id = record, entered_last_working_date = date }, cancellation);
        await tx.CommitAsync(cancellation);
        return (id,record);
    }

    private async Task<int> PrepareSettlementExitAsync(NpgsqlConnection db,NpgsqlTransaction tx,int employee,DateTime date,
        string reason,DateTime joining,DateTime today,int? selectedExit,CancellationToken cancellation)
    {
        if (date < joining)
            throw new InvalidOperationException("Last working date cannot precede the joining date.");
        var existing = await ReadExistingExitAsync(db,tx,employee,cancellation,selectedExit);
        if (existing.Id is int exit)
        {
            if (existing.Status is "Completed" or "Cancelled" && (existing.LastDay != date || reason.Length > 0))
                throw new InvalidOperationException("Use the recorded last working date and leave the exit reason blank for a closed case.");
            if (existing.LastDay != date || reason.Length > 0)
            {
                using var edit = new NpgsqlCommand(@"UPDATE public.exit_records x SET last_working_date=@date,
                    reason=coalesce(nullif(@reason,''),x.reason)
                    WHERE x.id=@exit AND x.employee_id=@employee AND x.xmin::text=@revision AND " + ExitOwnership,db,tx);
                SetScope(edit);
                edit.Parameters.AddWithValue("date",NpgsqlTypes.NpgsqlDbType.Date,date);
                edit.Parameters.AddWithValue("reason",reason);
                edit.Parameters.AddWithValue("exit",exit);
                edit.Parameters.AddWithValue("employee",employee);
                edit.Parameters.AddWithValue("revision",existing.Revision!);
                if (await edit.ExecuteNonQueryAsync(cancellation) != 1)
                    throw new InvalidOperationException("The current exit changed. Refresh before generating the settlement.");
            }
            return exit;
        }
        if (selectedExit.HasValue)
            throw new InvalidOperationException("The selected exit is unavailable for this employee.");
        using var create = new NpgsqlCommand(@"INSERT INTO public.exit_records
            (employee_id,exit_type,resignation_date,last_working_date,reason,status)
            VALUES(@employee,'Resignation',@today,@date,nullif(@reason,''),'Initiated') RETURNING id",db,tx);
        create.Parameters.AddWithValue("employee",employee);
        create.Parameters.AddWithValue("today",NpgsqlTypes.NpgsqlDbType.Date,today);
        create.Parameters.AddWithValue("date",NpgsqlTypes.NpgsqlDbType.Date,date);
        create.Parameters.AddWithValue("reason",reason);
        int created = (int)(await create.ExecuteScalarAsync(cancellation))!;
        await RecordOwnershipAsync(db,tx,"exit_records",created,cancellation);
        return created;
    }

    internal async Task SaveSettlementAdjustmentsAsync(int employee,int? record,int settlement,string revision,
        IEnumerable<EmployeeSettlementComponent> components,string remarks,CancellationToken cancellation)
    {
        remarks = remarks.Trim();
        var items = components.Where(item => !string.IsNullOrWhiteSpace(item.Name)).ToArray();
        if (remarks.Length > 1000 || items.Any(item => item.Name.Trim().Length > 120 || item.Source.Trim().Length > 80
            || item.Remarks.Trim().Length > 1000 || item.Amount is < 0 or > 9999999999.99m
            || item.Type is not ("earning" or "deduction")))
            throw new InvalidOperationException("Enter valid earning or deduction components, names, sources, nonnegative amounts and remarks.");

        var amounts = items.Select(item => Math.Round(item.Amount,2,MidpointRounding.AwayFromZero)).ToArray();
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await settings.VerifyWriteTargetAsync(db, tx, cancellation);
        await RequireSettlementGrantAsync(db, tx, actor, "edit", "payroll_run");
        await ReadExitEmployeeAsync(db, tx, employee, true, cancellation);
        using var command = SettlementQuery(@"UPDATE public.full_final_settlements s SET updated_at=now(),remarks=nullif(@remarks,''),
            other_payables=coalesce(s.other_earnings,0),other_recoveries=coalesce(s.other_deductions,0),
            net_payable=coalesce(nullif(@earnings,0),coalesce(s.unpaid_salary,0)+coalesce(s.leave_encashment_amount,0)
                +coalesce(s.gratuity_amount,0)+coalesce(s.reimbursement_payable,0)+coalesce(s.bonus_payable,0)
                +coalesce(nullif(s.other_earnings,0),s.other_payables,0))
                -coalesce(nullif(@deductions,0),coalesce(s.notice_recovery_amount,0)+coalesce(s.loan_recovery_amount,0)
                +coalesce(nullif(s.other_deductions,0),s.other_recoveries,0)) WHERE ",
            @" AND s.id=@settlement AND s.xmin::text=@revision
                AND replace(lower(btrim(coalesce(s.status,'draft'))),' ','_') IN ('draft','rejected')",
            db, tx, employee, record);
        command.Parameters.AddWithValue("settlement",settlement);
        command.Parameters.AddWithValue("revision",revision);
        command.Parameters.AddWithValue("remarks",remarks);
        command.Parameters.AddWithValue("earnings",amounts.Where((_,index) => items[index].Type == "earning").Sum());
        command.Parameters.AddWithValue("deductions",amounts.Where((_,index) => items[index].Type == "deduction").Sum());
        if (await command.ExecuteNonQueryAsync(cancellation) != 1)
            throw new InvalidOperationException("Only the current draft or rejected settlement can be adjusted. Refresh and try again.");

        using var lines = new NpgsqlCommand(@"
            DELETE FROM public.full_final_settlement_lines WHERE settlement_id=@settlement;
            INSERT INTO public.full_final_settlement_lines(settlement_id,line_type,component_name,amount,source,is_manual_adjustment,remarks)
            SELECT @settlement,t.type,t.name,t.amount,nullif(t.source,''),t.manual,nullif(t.remarks,'')
            FROM unnest(@types,@names,@amounts,@sources,@manual,@remarks) AS t(type,name,amount,source,manual,remarks)",db,tx);
        lines.Parameters.AddWithValue("settlement",settlement);
        lines.Parameters.AddWithValue("types",items.Select(item => item.Type).ToArray());
        lines.Parameters.AddWithValue("names",items.Select(item => item.Name.Trim()).ToArray());
        lines.Parameters.AddWithValue("amounts",amounts);
        lines.Parameters.AddWithValue("sources",items.Select(item => item.Source.Trim()).ToArray());
        lines.Parameters.AddWithValue("manual",items.Select(item => item.Manual).ToArray());
        lines.Parameters.AddWithValue("remarks",items.Select(item => item.Remarks.Trim()).ToArray());
        await lines.ExecuteNonQueryAsync(cancellation);
        await RecordExitAuditAsync(db,tx,actor.Id,employee,"SETTLEMENT_ADJUSTED","Final settlement adjustments saved",
            new { settlement_id = settlement, exit_id = record, component_count = items.Length },cancellation);
        await tx.CommitAsync(cancellation);
    }

    internal async Task DecideSettlementAsync(int employee, int? record, int settlement, string revision, string action,
        string remarks, CancellationToken cancellation)
    {
        remarks = remarks.Trim();
        if (remarks.Length > 1000)
            throw new InvalidOperationException("Use at most 1,000 characters for remarks.");
        var (previous, next, changes, permissions) = action switch
        {
            "Submit" => ("draft,rejected", "pending_approval", "submitted_at=now()", new[] { "payroll_run" }),
            "Approve" => ("pending_approval", "approved", "approved_at=now(),approved_by=@actor", new[] { "payroll_approve" }),
            "Reject" => ("pending_approval", "rejected", "rejected_at=now(),rejected_by=@actor", new[] { "payroll_approve" }),
            "Mark paid" => ("approved", "paid", "paid_at=now()", new[] { "payroll_approve", "payroll_run" }),
            _ => throw new InvalidOperationException("Choose a settlement action.")
        };

        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await settings.VerifyWriteTargetAsync(db, tx, cancellation);
        await RequireSettlementGrantAsync(db, tx, actor, "edit", permissions);
        var current = await ReadExitEmployeeAsync(db, tx, employee, true, cancellation);
        using var update = SettlementQuery(@"UPDATE public.full_final_settlements s SET status=@next,updated_at=now(),
            remarks=coalesce(nullif(@remarks,''),s.remarks)," + changes + " WHERE ",
            @" AND s.id=@settlement AND s.xmin::text=@revision
                AND replace(lower(btrim(coalesce(s.status,'draft'))),' ','_')=ANY(@previous) RETURNING s.net_payable", db, tx, employee, record);
        update.Parameters.AddWithValue("next", next);
        update.Parameters.AddWithValue("remarks", remarks);
        update.Parameters.AddWithValue("actor", actor.Id);
        update.Parameters.AddWithValue("settlement", settlement);
        update.Parameters.AddWithValue("revision", revision);
        update.Parameters.AddWithValue("previous", previous.Split(','));
        object? net = await update.ExecuteScalarAsync(cancellation);
        if (net is null)
            throw new InvalidOperationException("The settlement state changed or this action is unavailable. Refresh and try again.");
        if (next == "paid" && record is int linkedExit)
        {
            if (net is DBNull)
                throw new InvalidOperationException("The settlement has no net payable amount.");
            using var updateExit = new NpgsqlCommand(@"UPDATE public.exit_records x SET status='Completed',
                final_settlement_amount=@net,final_settlement_date=@today WHERE x.id=@record AND x.employee_id=@employee
                AND " + ExitOwnership, db, tx);
            SetScope(updateExit);
            updateExit.Parameters.AddWithValue("employee", employee);
            updateExit.Parameters.AddWithValue("record", linkedExit);
            updateExit.Parameters.AddWithValue("net", net);
            updateExit.Parameters.AddWithValue("today", NpgsqlTypes.NpgsqlDbType.Date, current.Today);
            if (await updateExit.ExecuteNonQueryAsync(cancellation) != 1)
                throw new InvalidOperationException("The linked exit case is no longer available.");
        }
        await RecordExitAuditAsync(db, tx, actor.Id, employee, "SETTLEMENT_" + next.ToUpperInvariant(),
            "Final settlement " + next.Replace('_', ' '), new { settlement_id = settlement, exit_id = record }, cancellation);
        await tx.CommitAsync(cancellation);
    }

    internal async Task<(string Template, string? Logo, string? Signature, bool Available, string Company)> ReadSettlementPresentationAsync(
        CancellationToken cancellation, bool preview = false)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await settings.RequireActorAsync(db,tx,cancellation);
        string company = "";
        if (preview)
        {
            await RequireSettlementGrantAsync(db,tx,actor,"view","payroll_view","payroll_run");
            using var readCompany = new NpgsqlCommand("SELECT name FROM public.companies WHERE id=@company",db,tx);
            readCompany.Parameters.AddWithValue("company",settings.OrganizationId);
            company = (string?)await readCompany.ExecuteScalarAsync(cancellation) ?? "";
        }
        using var query = new NpgsqlCommand(@"
            SELECT coalesce(settlement_template::text,'{}'),branding->>'logo',branding->>'signature'
            FROM public.payroll_delivery_profiles WHERE company_id=@company",db,tx);
        query.Parameters.AddWithValue("company",settings.OrganizationId);
        try
        {
            using var row = await query.ExecuteReaderAsync(cancellation);
            if (await row.ReadAsync(cancellation))
                return (row.GetString(0),row.IsDBNull(1) ? null : row.GetString(1),row.IsDBNull(2) ? null : row.GetString(2),true,company);
            return ("{}",null,null,true,company);
        }
        catch (PostgresException ex) when (ex.SqlState is "42501" or "42P01")
        {
            return ("{}",null,null,false,company);
        }
    }

    internal byte[]? ReadSettlementBrandAsset(string? reference, string kind)
    {
        if (reference is null || string.IsNullOrWhiteSpace(reference))
            return null;
        string[] parts = reference.Replace('\\','/').Split('/');
        if (parts.Length != 3 || parts[0] != "payroll-branding" ||
            parts[1] != settings.OrganizationId.ToString(System.Globalization.CultureInfo.InvariantCulture) ||
            parts[2].Length != kind.Length + 37 || !parts[2].StartsWith(kind + "_",StringComparison.Ordinal) ||
            !parts[2].EndsWith(".png",StringComparison.OrdinalIgnoreCase) ||
            !Guid.TryParseExact(parts[2].Substring(kind.Length + 1, parts[2].Length - kind.Length - 5),"N",out _))
            return null;
        try
        {
            string folderPath = Path.Combine(settings.DocumentsRoot,parts[0],parts[1]);
            for (DirectoryInfo? folder = new DirectoryInfo(folderPath); folder is not null; folder = folder.Parent)
                if (folder.Exists && (folder.Attributes & FileAttributes.ReparsePoint) != 0)
                    return null;
            var file = new FileInfo(Path.Combine(folderPath,parts[2]));
            if (!file.Exists || (file.Attributes & FileAttributes.ReparsePoint) != 0 || file.Length is < 24 or > 52_428_800)
                return null;
            var bytes = File.ReadAllBytes(file.FullName);
            if (bytes.Length < 24 || !bytes.Take(16).SequenceEqual(
                new byte[] { 137,80,78,71,13,10,26,10,0,0,0,13,73,72,68,82 }))
                return null;
            long width = PngDimension(16);
            long height = PngDimension(20);
            return width is > 0 and <= 12_000_000 && height is > 0 and <= 12_000_000 && width * height <= 12_000_000
                ? bytes : null;

            long PngDimension(int start) => (((long)bytes[start] << 24) | ((long)bytes[start + 1] << 16)
                | ((long)bytes[start + 2] << 8) | bytes[start + 3]);
        }
        catch (IOException) { return null; }
        catch (UnauthorizedAccessException) { return null; }
    }

    private NpgsqlCommand SettlementQuery(string sql, string tail, NpgsqlConnection db, NpgsqlTransaction tx, int employee, int? record)
    {
        var query = new NpgsqlCommand(sql + @"s.organization_id=@company AND s.employee_id=@employee
            AND s.exit_record_id IS NOT DISTINCT FROM @record AND " + SettlementExitScope + tail, db, tx);
        SetScope(query);
        query.Parameters.AddWithValue("employee", employee);
        query.Parameters.AddWithValue("record",NpgsqlTypes.NpgsqlDbType.Integer,(object?)record ?? DBNull.Value);
        return query;
    }

    private async Task<bool> CanChangeSettlementAsync(NpgsqlConnection db, NpgsqlTransaction tx, DesktopActor actor, params string[] permissions)
    {
        try
        {
            await RequireSettlementGrantAsync(db, tx, actor, "edit", permissions);
            return true;
        }
        catch (UnauthorizedAccessException) { return false; }
    }

    private async Task RequireSettlementGrantAsync(NpgsqlConnection db, NpgsqlTransaction tx, DesktopActor actor,
        string operation, params string[] permissions)
    {
        int branch = settings.BranchId ?? throw new InvalidOperationException("Choose a branch to view settlements.");
        var grant = await DesktopModuleAccess.RequireAsync(db, tx, settings.OrganizationId, branch, actor, "hrms", operation, permissions);
        if (grant.Scope is not ("organization" or "branch"))
            throw new UnauthorizedAccessException("Final settlements require organization or branch payroll access.");
    }
}
