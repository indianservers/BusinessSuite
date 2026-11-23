using System.Data;
using System.Globalization;

namespace Business_Suite;

internal sealed record CrmDealHealth(int Score,string Level,int DealAge,int StageAge,int? ActivityGap,string[] Reasons)
{
    internal static CrmDealHealth Evaluate(DataRow deal,DateTime now)
    {
        int? Age(string name)=>deal[name] is DateTime stamp?Math.Max(0,(now-Utc(stamp)).Days):null;
        int dealAge=Age("created_at")??0;
        int stageAge=Age("stage_entered_at")??dealAge;
        int? activity=Age("last_activity_at");
        int threshold=int.TryParse(deal["stagnation_days"] as string,NumberStyles.None,CultureInfo.InvariantCulture,out int stored)
            && stored is >=1 and <=365?stored:14;
        var reasons=new List<string>();
        int score=100;
        if (deal["status"] is "Open")
        {
            if (deal["next_follow_up_at"] is DateTime followUp)
            {
                if (Utc(followUp)<now)
                    Deduct(30,"Follow-up overdue");
            }
            else Deduct(20,"No next action scheduled");
            if (!activity.HasValue)
                Deduct(20,"No recorded last activity");
            else if (activity>=14)
                Deduct(25,$"No activity for {activity} days");
            if (deal["expected_close_date"] is DateTime closeDate && closeDate.Date<now.Date)
                Deduct(25,"Expected closing date has passed");
            if (stageAge>=threshold)
                Deduct(15,$"Current stage has exceeded its {threshold}-day stagnation threshold");
            if (dealAge>=90)
                Deduct(10,$"Deal has been open {dealAge} days");
        }
        score=Math.Max(0,score);
        string level=score<=30?"Critical":score<=50?"At Risk":score<=75?"Needs Attention":"Healthy";
        return new(score,level,dealAge,stageAge,activity,reasons.ToArray());

        void Deduct(int penalty,string reason)
        {
            score-=penalty;
            reasons.Add(reason);
        }

        static DateTime Utc(DateTime value)=>value.Kind==DateTimeKind.Local?value.ToUniversalTime():DateTime.SpecifyKind(value,DateTimeKind.Utc);
    }

    internal static void AddColumns(DataTable rows,DateTime now)
    {
        rows.Columns.Add("health_score",typeof(int));
        rows.Columns.Add("health_level",typeof(string));
        rows.Columns.Add("health_display",typeof(string));
        foreach (DataRow row in rows.Rows)
        {
            var result=Evaluate(row,now);
            row["health_score"]=result.Score;
            row["health_level"]=result.Level;
            row["health_display"]=$"{result.Score} · {result.Level}";
        }
        rows.AcceptChanges();
    }
}
