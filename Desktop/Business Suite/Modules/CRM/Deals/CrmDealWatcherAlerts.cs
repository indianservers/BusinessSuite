using System.Data;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class CrmDealRepository
{
    private async Task NotifyDealWatchersAsync(NpgsqlConnection db,NpgsqlTransaction tx,int author,DataRow deal,string name,
        CancellationToken cancellation)
    {
        int id=(int)deal["id"];
        int? branch=deal["owning_branch"] as int?;
        using var watching=Query(db,tx,@"SELECT DISTINCT user_id FROM public.crm_deal_collaborators
            WHERE organization_id=@org AND deal_id=@id AND user_id<>@author AND watching ORDER BY user_id",
            ("id",NpgsqlDbType.Integer,id),("author",NpgsqlDbType.Integer,author));
        var watchers=await ReadAsync(watching,cancellation);
        foreach (DataRow entry in watchers.Rows)
        {
            int recipient=(int)entry["user_id"];
            var candidates=await LeadStore.LeadOwnerCandidatesAsync(db,tx,settings.OrganizationId,branch ?? 0,recipient,true,cancellation);
            if (candidates.Count!=1) continue;
            var recipientRepository=branch==settings.BranchId?this:new CrmDealRepository(settings.ForScope(settings.OrganizationId,branch));
            try
            {
                await recipientRepository.RequireDealsAsync(db,tx,candidates[0].Actor,false);
            }
            catch (UnauthorizedAccessException) { continue; }
            using var notification=Query(db,tx,@"WITH alert AS (
                INSERT INTO public.notifications(company_id,user_id,module,event_type,related_entity_type,related_entity_id,
                    title,message,action_url,channels,priority,is_read)
                VALUES (@org,@recipient,'crm','deal.updated','deal',@id,'Watched deal updated',@message,@url,'[""in_app""]'::json,'normal',false)
                RETURNING id)
                INSERT INTO public.suite_branch_ownership(resource_table,resource_key,company_id,branch_id,source)
                SELECT 'notifications',id::text,@org,@branch,'desktop-crm' FROM alert WHERE @branch IS NOT NULL",
                ("recipient",NpgsqlDbType.Integer,recipient),("id",NpgsqlDbType.Integer,id),
                ("branch",NpgsqlDbType.Integer,branch),("url",NpgsqlDbType.Text,$"/crm/deals/{id}"),
                ("message",NpgsqlDbType.Text,$"{name} was updated by user #{author} (revision {(int)deal["version"]+1})."));
            await notification.ExecuteNonQueryAsync(cancellation);
        }
    }
}
