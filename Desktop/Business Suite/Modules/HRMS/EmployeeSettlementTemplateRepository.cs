using System.Data;
using System.Text.Json;
using Npgsql;

namespace Business_Suite;

internal sealed record EmployeeSettlementTemplate(string Layout, bool ShowCode, string Footer, string Revision, bool CanSave,
    PayrollYearPolicy Year);

internal sealed record PayrollYearPolicy(string Basis, int FinancialYearStart);

internal sealed partial class EmployeeAdministrationRepository
{
    internal async Task<EmployeeSettlementTemplate> ReadSettlementTemplateAsync(CancellationToken cancellation)
    {
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction(IsolationLevel.RepeatableRead);
        var actor = await settings.RequireActorAsync(db,tx,cancellation);
        await RequireSettlementGrantAsync(db,tx,actor,"view","payroll_run","payroll_view","payroll_approve");
        bool canSave = false;
        if (actor.CanWriteBranch)
        {
            try
            {
                await RequireSettlementTemplateWriteAsync(db,tx,actor);
                canSave = true;
            }
            catch (UnauthorizedAccessException) { }
        }

        using var query = new NpgsqlCommand(@"SELECT xmin::text,coalesce(settlement_template::text,'{}'),ytd_basis,fy_start_month
            FROM public.payroll_delivery_profiles WHERE company_id=@company",db,tx);
        query.Parameters.AddWithValue("company",settings.OrganizationId);
        using var row = await query.ExecuteReaderAsync(cancellation);
        if (!await row.ReadAsync(cancellation))
            return new("standard",true,"Confidential - employee payslip","",canSave,new PayrollYearPolicy("financial",4));
        using var json = JsonDocument.Parse(row.GetString(1));
        var root = json.RootElement;
        string Text(string key, string fallback) => root.ValueKind == JsonValueKind.Object &&
            root.TryGetProperty(key,out var value) && value.ValueKind == JsonValueKind.String ? value.GetString() ?? fallback : fallback;
        bool showCode = root.ValueKind != JsonValueKind.Object || !root.TryGetProperty("show_employee_code",out var code)
            || code.ValueKind != JsonValueKind.False;
        return new(Text("layout","standard"),showCode,Text("footer","Confidential - employee payslip"),row.GetString(0),canSave,
            new PayrollYearPolicy(row.GetString(2),row.GetInt32(3)));
    }

    internal async Task SaveSettlementTemplateAsync(string layout,bool showCode,string footer,string revision,CancellationToken cancellation,
        PayrollYearPolicy? year = null)
    {
        if (layout is not ("standard" or "compact" or "professional") || footer.Length > 300)
            throw new InvalidOperationException("Choose a valid layout and enter a footer of at most 300 characters.");
        if (year is not null && (year.Basis is not ("financial" or "calendar") || year.FinancialYearStart is < 1 or > 12))
            throw new InvalidOperationException("Choose a valid payslip YTD basis and financial-year start month.");
        using var db = new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx = db.BeginTransaction();
        var actor = await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await RequireSettlementTemplateWriteAsync(db,tx,actor);
        const string patch = "jsonb_build_object('layout',@layout,'show_employee_code',@code,'footer',@footer)";
        string sql = revision.Length == 0
            ? @"INSERT INTO public.payroll_delivery_profiles(company_id,ytd_basis,fy_start_month,regular_template,settlement_template,
                   branding,payout_mode,updated_by,updated_at)
                VALUES(@company,coalesce(@basis,'financial'),coalesce(@month,4),'{}',(" + patch + @")::json,'{}','test',@actor,now())
                ON CONFLICT(company_id) DO NOTHING"
            : @"UPDATE public.payroll_delivery_profiles SET
                   ytd_basis=coalesce(@basis,ytd_basis),fy_start_month=coalesce(@month,fy_start_month),
                   settlement_template=(coalesce(settlement_template::jsonb,'{}'::jsonb) || " + patch + @")::json,
                   updated_by=@actor,updated_at=now()
                WHERE company_id=@company AND xmin::text=@revision";
        using var save = new NpgsqlCommand(sql,db,tx);
        save.Parameters.AddWithValue("company",settings.OrganizationId);
        save.Parameters.AddWithValue("layout",layout);
        save.Parameters.AddWithValue("code",showCode);
        save.Parameters.AddWithValue("footer",footer);
        save.Parameters.AddWithValue("actor",actor.Id);
        save.Parameters.AddWithValue("revision",revision);
        SetYearArguments(save,year);
        if (await save.ExecuteNonQueryAsync(cancellation) != 1)
            throw new InvalidOperationException("The payroll template changed. Reload before saving again.");

        using var audit = new NpgsqlCommand(@"INSERT INTO public.suite_access_audit
            (actor_id,company_id,operation,reason,outcome,after_json)
            VALUES(@actor,@company,'payroll_presentation_updated','Payroll presentation settings','success',
                (" + patch + @" || jsonb_strip_nulls(jsonb_build_object('ytd_basis',@basis,'fy_start_month',@month)))::json)",db,tx);
        audit.Parameters.AddWithValue("company",settings.OrganizationId);
        audit.Parameters.AddWithValue("actor",actor.Id);
        audit.Parameters.AddWithValue("layout",layout);
        audit.Parameters.AddWithValue("code",showCode);
        audit.Parameters.AddWithValue("footer",footer);
        SetYearArguments(audit,year);
        await audit.ExecuteNonQueryAsync(cancellation);
        await tx.CommitAsync(cancellation);
    }

    private static void SetYearArguments(NpgsqlCommand command, PayrollYearPolicy? year)
    {
        command.Parameters.AddWithValue("basis",NpgsqlTypes.NpgsqlDbType.Text,(object?)year?.Basis ?? DBNull.Value);
        command.Parameters.AddWithValue("month",NpgsqlTypes.NpgsqlDbType.Integer,(object?)year?.FinancialYearStart ?? DBNull.Value);
    }

    private async Task RequireSettlementTemplateWriteAsync(NpgsqlConnection db,NpgsqlTransaction tx,DesktopActor actor)
    {
        int branch = settings.BranchId ?? throw new InvalidOperationException("Choose a branch before editing payroll templates.");
        var grant = await DesktopModuleAccess.RequireAsync(db,tx,settings.OrganizationId,branch,actor,"hrms","edit","payroll_run");
        if (grant.Scope != "organization")
            throw new UnauthorizedAccessException("Company payroll templates require organization-wide payroll processing access.");
    }
}
