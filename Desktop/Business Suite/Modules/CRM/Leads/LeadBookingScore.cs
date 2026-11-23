using System.Data;
using System.Globalization;
using System.Text;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record LeadScoreReason(int RuleId,string Name,bool Matched,int Points);
internal sealed record LeadScoreResult(int Score,string Label,List<LeadScoreReason> Reasons);
internal sealed record LeadScoringRule(int Id,string Name,string Field,string Operator,string Value,int Points);
internal sealed record LeadScoreBatchResult(int Updated,int Manual);

internal static partial class LeadStore
{
    private static async Task<LeadScoreResult> RefreshLeadScoreAsync(NpgsqlConnection db,NpgsqlTransaction tx,int org,
        DataRow lead,int actor,DateTime now,CancellationToken cancellation,bool force=false)
    {
        bool manual=!force&&string.Equals(lead["lead_score_mode"] as string,"manual",StringComparison.OrdinalIgnoreCase);
        LeadScoreResult result=manual?new(lead["lead_score"] as int? ?? 0,Text(lead,"lead_score_label"),[]):
            EvaluateLeadScore(lead,await ReadLeadScoringRulesAsync(db,tx,org,actor,cancellation),now);
        using var update=Cmd(db,tx,@"UPDATE public.crm_leads SET updated_at=@now,updated_by_user_id=@actor,
             lead_score=CASE WHEN @manual THEN lead_score ELSE @score END,
             lead_score_label=CASE WHEN @manual THEN lead_score_label ELSE @label END,
             rating=CASE WHEN @manual THEN rating ELSE @label END,
             lead_score_mode=CASE WHEN @manual THEN lead_score_mode ELSE 'automatic' END,
             last_score_calculated_at=CASE WHEN @manual THEN last_score_calculated_at ELSE @now END
             WHERE organization_id=@org AND id=@lead",
            ("now",NpgsqlDbType.TimestampTz,now),("actor",NpgsqlDbType.Integer,actor),("manual",NpgsqlDbType.Boolean,manual),
            ("score",NpgsqlDbType.Integer,result.Score),("label",NpgsqlDbType.Text,result.Label),("org",NpgsqlDbType.Integer,org),
            ("lead",NpgsqlDbType.Integer,lead["id"]));
        await update.ExecuteNonQueryAsync(cancellation);
        return result;
    }

    private static async Task<List<LeadScoringRule>> ReadLeadScoringRulesAsync(NpgsqlConnection db,NpgsqlTransaction tx,
        int org,int actor,CancellationToken cancellation)
    {
        using(var seed=Cmd(db,tx,@"INSERT INTO public.crm_lead_scoring_rules
                (organization_id,name,field,operator,value,points,is_active,created_by_user_id,updated_by_user_id)
                SELECT @org,rule.name,rule.field,rule.op,rule.value,rule.points,true,@actor,@actor
                FROM (VALUES ('Has email','email','exists','',10),('Has phone','phone','exists','',10),
                    ('Company provided','company_name','exists','',10),('Source is website','source','equals','Website',10),
                    ('Budget above threshold','estimated_value','gte','500000',15),
                    ('No activity in 30 days','last_contacted_at','older_than_days','30',-10)) rule(name,field,op,value,points)
                WHERE NOT EXISTS (SELECT 1 FROM public.crm_lead_scoring_rules WHERE organization_id=@org)
                ON CONFLICT (organization_id,name) DO NOTHING",
                ("org",NpgsqlDbType.Integer,org),("actor",NpgsqlDbType.Integer,actor)))
            await seed.ExecuteNonQueryAsync(cancellation);
        using var query=Cmd(db,tx,@"SELECT id,name,field,lower(operator),COALESCE(value,''),points
            FROM public.crm_lead_scoring_rules WHERE organization_id=@org AND deleted_at IS NULL AND is_active=true ORDER BY id",
            ("org",NpgsqlDbType.Integer,org));
        var rules=new List<LeadScoringRule>();
        using var rows=await query.ExecuteReaderAsync(cancellation);
        while (await rows.ReadAsync(cancellation))
            rules.Add(new(rows.GetInt32(0),rows.GetString(1),ScoringField(rows.GetString(2)),rows.GetString(3),
                rows.GetString(4),rows.GetInt32(5)));
        return rules;
    }

    private static LeadScoreResult EvaluateLeadScore(DataRow lead,List<LeadScoringRule> rules,DateTime now)
    {
        var reasons=new List<LeadScoreReason>();
        long total=0;
        foreach(var rule in rules)
        {
            string field=rule.Field;
            object? actual=field=="updated_at"?now:lead.Table.Columns.Contains(field)&&!lead.IsNull(field)?lead[field]:null;
            bool matched=ScoreRuleMatches(actual,field,rule.Operator,rule.Value,now);
            int points=matched?rule.Points:0;
            reasons.Add(new(rule.Id,rule.Name,matched,points));
            total+=points;
        }
        int score=(int)Math.Min(100,Math.Max(0,total));
        return new(score,LeadScoreLabel(score),reasons);
    }

    internal static async Task<LeadScoreResult> RecalculateLeadScoreAsync(LeadKey key,bool replaceManual,CancellationToken cancellation)
    {
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await RequireLeadScoreWriteAsync(db,tx,settings,actor);
        var lead=await LockLead(db,tx,settings,key,false,cancellation);
        if (!replaceManual&&string.Equals(lead["lead_score_mode"] as string,"manual",StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("Confirm replacement of the manual score before recalculating.");
        int org=settings.OrganizationId;
        var result=await RefreshLeadScoreAsync(db,tx,org,lead,actor.Id,DateTime.UtcNow,cancellation,force:true);
        await CrmDirectoryWrites.Audit(db,tx,"crm_leads",org,key.Id,actor.Id,"UPDATE",cancellation,
            $"Lead score recalculated to {result.Score} ({result.Label})");
        tx.Commit();
        return result;
    }

    internal static async Task<LeadScoreBatchResult> RecalculateAutomaticLeadScoresAsync(CancellationToken cancellation)
    {
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await RequireLeadScoreWriteAsync(db,tx,settings,actor);
        int org=settings.OrganizationId;
        using var select=Cmd(db,tx,@"SELECT l.* FROM public.crm_leads l
            LEFT JOIN public.crm_lead_operating_states s ON s.organization_id=l.organization_id AND s.lead_id=l.id
            WHERE l.organization_id=@org AND l.deleted_at IS NULL AND COALESCE(s.data_json->>'archived','false')<>'true'
                AND "+CrmDirectoryWrites.BranchScope("crm_leads","l")+@"
            ORDER BY l.id FOR UPDATE OF l",
            ("org",NpgsqlDbType.Integer,org),("scope_branch",NpgsqlDbType.Integer,settings.BranchId));
        DataTable rows;
        using(var reader=await select.ExecuteReaderAsync(cancellation))
            rows=await Table(reader,cancellation);
        var automatic=rows.Rows.Cast<DataRow>().Where(lead=>
            !string.Equals(lead["lead_score_mode"] as string,"manual",StringComparison.OrdinalIgnoreCase)).ToArray();
        int manual=rows.Rows.Count-automatic.Length;
        if (automatic.Length==0)
            return new(0,manual);
        var rules=await ReadLeadScoringRulesAsync(db,tx,org,actor.Id,cancellation);
        DateTime now=DateTime.UtcNow;
        var ids=new int[automatic.Length];
        var scores=new int[automatic.Length];
        var labels=new string[automatic.Length];
        for(int i=0;i<automatic.Length;i++)
        {
            cancellation.ThrowIfCancellationRequested();
            ids[i]=(int)automatic[i]["id"];
            var score=EvaluateLeadScore(automatic[i],rules,now);
            scores[i]=score.Score;
            labels[i]=score.Label;
        }
        using var save=Cmd(db,tx,@"WITH scores AS (
                SELECT * FROM unnest(@ids,@scores,@labels) AS x(id,score,label)
            ), updated AS (
                UPDATE public.crm_leads l SET lead_score=s.score,lead_score_label=s.label,rating=s.label,lead_score_mode='automatic',
                    last_score_calculated_at=@now,updated_at=@now,updated_by_user_id=@actor
                FROM scores s WHERE l.organization_id=@org AND l.id=s.id RETURNING l.id,l.lead_score,l.lead_score_label
            ) INSERT INTO public.audit_logs(organization_id,user_id,actor_authenticated,method,entity_type,entity_id,
                action,description,module)
            SELECT @org,@actor,true,'CRM','crm_leads',id,'UPDATE',
                'Business Suite Desktop · Batch Lead score recalculated to '||lead_score||' ('||lead_score_label||')','crm' FROM updated",
            ("org",NpgsqlDbType.Integer,org),("actor",NpgsqlDbType.Integer,actor.Id),("now",NpgsqlDbType.TimestampTz,now),
            ("ids",NpgsqlDbType.Array|NpgsqlDbType.Integer,ids),("scores",NpgsqlDbType.Array|NpgsqlDbType.Integer,scores),
            ("labels",NpgsqlDbType.Array|NpgsqlDbType.Text,labels));
        int updated=await save.ExecuteNonQueryAsync(cancellation);
        if (updated!=automatic.Length)
            throw new InvalidOperationException("Lead scores changed during processing. Refresh and try again.");
        tx.Commit();
        return new(updated,manual);
    }

    internal static async Task<LeadScoreResult> SetManualLeadScoreAsync(LeadKey key,int score,string reason,
        CancellationToken cancellation)
    {
        reason=reason.Trim();
        if (score is <0 or >100)
            throw new ArgumentException("Enter a Lead score between 0 and 100.");
        if (reason.Length is <1 or >1000)
            throw new ArgumentException("Explain the manual score override in up to 1,000 characters.");
        var settings=DesktopDatabaseSettings.Load();
        using var db=new NpgsqlConnection(settings.ConnectionString);
        await db.OpenAsync(cancellation);
        using var tx=db.BeginTransaction();
        var actor=await settings.VerifyWriteTargetAsync(db,tx,cancellation);
        await CrmDirectoryWrites.RequireCrmAccessAsync(settings,db,tx,actor,"leads","edit");
        var lead=await LockLead(db,tx,settings,key,false,cancellation);
        int org=settings.OrganizationId;
        var details=ReadDetails(lead);
        details["scoreOverrideReason"]=reason;
        var policy=await ReadPolicy(db,tx,org,cancellation);
        ValidateTransition(policy,lead,Text(lead,"status"),
            new Dictionary<string,string> { ["lead_score"]=score.ToString(CultureInfo.InvariantCulture) },details,false);
        await CrmDirectoryWrites.CheckRequiredFieldsAsync(db,tx,"leads",org,key.Id,cancellation);
        string label=LeadScoreLabel(score);
        await WriteState(db,tx,org,key.Id,details,key.StateRevision,cancellation);
        using var update=Cmd(db,tx,@"UPDATE public.crm_leads SET lead_score=@score,lead_score_label=@label,
            rating=@label,lead_score_mode='manual',updated_by_user_id=@actor,updated_at=now()
            WHERE organization_id=@org AND id=@lead",
            ("org",NpgsqlDbType.Integer,org),("lead",NpgsqlDbType.Integer,key.Id),("score",NpgsqlDbType.Integer,score),
            ("label",NpgsqlDbType.Text,label),("actor",NpgsqlDbType.Integer,actor.Id));
        await update.ExecuteNonQueryAsync(cancellation);
        await AddLeadHistoryAsync(db,tx,org,key.Id,settings.BranchId??lead["branch_id"] as int?,actor.Id,
            "updated","Lead updated",null,JsonSerializer.Serialize(new {
                before=new { lead_score=lead["lead_score"] as int? },fields=new[] {"lead_score"},details=new[] {"scoreOverrideReason"}
            }),cancellation);
        await CrmDirectoryWrites.Audit(db,tx,"crm_leads",org,key.Id,actor.Id,"UPDATE",cancellation,
            $"Manual Lead score set to {score} ({label})");
        tx.Commit();
        return new(score,label,[]);
    }

    private static string LeadScoreLabel(int score) => score<=30?"Cold":score<=70?"Warm":"Hot";

    private static async Task RequireLeadScoreWriteAsync(NpgsqlConnection db,NpgsqlTransaction tx,
        DesktopDatabaseSettings settings,DesktopActor actor)
    {
        CrmDirectoryWrites.RequireCrmAccess(actor);
        var grant=await DesktopModuleAccess.RequireAsync(db,tx,settings.OrganizationId,settings.BranchId??0,actor,
            "crm","edit","crm_manage","crm_admin");
        if (grant.Scope is not ("organization" or "branch") || (grant.Scope=="branch"&&!settings.BranchId.HasValue))
            throw new UnauthorizedAccessException("Lead score recalculation requires branch or organization CRM management access.");
    }

    private static string ScoringField(string field)
    {
        var name=new StringBuilder(field.Length);
        for (int i=0;i<field.Length;i++)
        {
            char letter=field[i];
            if (i>0&&char.IsUpper(letter))
                name.Append('_');
            name.Append(letter=='-'?'_':char.ToLowerInvariant(letter));
        }
        return name.ToString();
    }

    private static bool ScoreRuleMatches(object? actual,string field,string op,string expected,DateTime now)
    {
        bool empty=actual is null or "";
        string text=actual is false or 0 or 0m?"":Convert.ToString(actual,CultureInfo.InvariantCulture)??"";
        return op switch
        {
            "exists" or "has_value"=>!empty,
            "not_exists" or "empty"=>empty,
            "equals" or "eq" or "is"=>string.Equals(text,expected,StringComparison.OrdinalIgnoreCase),
            "not_equals" or "neq"=>!string.Equals(text,expected,StringComparison.OrdinalIgnoreCase),
            "contains"=>text.IndexOf(expected,StringComparison.OrdinalIgnoreCase)>=0,
            "gt" or "gte" or "lt" or "lte"=>CompareScoreNumbers(text,expected,op),
            "older_than_days"=>actual is DateTime instant&&field!="expected_close_date"
                ?int.TryParse(expected.Length==0?"0":expected,NumberStyles.Integer,CultureInfo.InvariantCulture,out int days)
                    &&Math.Floor((now-instant.ToUniversalTime()).TotalDays)>=days
                :empty,
            _=>false
        };
    }

    private static bool CompareScoreNumbers(string text,string expected,string op)
    {
        if (!decimal.TryParse(text.Length==0?"0":text,NumberStyles.Float,CultureInfo.InvariantCulture,out decimal number) ||
            !decimal.TryParse(expected.Length==0?"0":expected,NumberStyles.Float,CultureInfo.InvariantCulture,out decimal target))
            return false;
        return op switch { "gt"=>number>target,"gte"=>number>=target,"lt"=>number<target,_=>number<=target };
    }
}
