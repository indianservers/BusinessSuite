using Npgsql;

namespace Business_Suite;

internal static class SalesReadAccess
{
    internal static async Task<string> OrderScopeAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        int company, int branch, DesktopActor actor, string action = "view", bool invoiceDraft = false, bool invoiceView = false, bool collection = false)
    {
        string[] permissions = collection ? new[] { "srm_collection_create", "srm_admin" } : invoiceView ? new[] { "srm_invoice_view", "srm_invoice_create", "srm_invoice_approve", "srm_admin" } : invoiceDraft ? new[] { "srm_invoice_create", "srm_admin" } : action switch
        {
            "view" => new[] { "srm_view", "srm_manage", "srm_admin" },
            "approve" => new[] { "srm_invoice_approve", "srm_admin" },
            _ => new[] { "srm_manage", "srm_admin" }
        };
        return await OrderScopeForPermissionsAsync(db, tx, company, branch, actor, action, permissions);
    }

    internal static async Task<string> OrderScopeForPermissionsAsync(NpgsqlConnection db, NpgsqlTransaction tx,
        int company, int branch, DesktopActor actor, string action, params string[] permissions)
    {
        var grant = await DesktopModuleAccess.RequireAsync(db, tx, company, branch, actor, "srm", action, permissions);
        return !grant.IsLegacy || grant.LegacyRole is "srm_admin" or "srm_sales_manager" or "srm_finance_manager"
            or "srm_revenue_manager" or "srm_business_owner" or "srm_viewer" or "super_admin"
            ? grant.Scope : "legacy_assigned";
    }
}
