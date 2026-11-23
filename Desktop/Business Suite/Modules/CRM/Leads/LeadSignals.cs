using System.Data;
using System.Globalization;

namespace Business_Suite;

internal sealed record LeadSignals(bool Active,bool Overdue,bool SlaBreached,bool Stale,DateTime Deadline,string NextAction,
    string FollowUpLabel)
{
    internal static LeadSignals Evaluate(DataRow row,LeadPolicy policy,DateTime now)
    {
        DateTime? Stamp(string field)=>row[field] is DateTime value
            ?value.Kind==DateTimeKind.Local?value.ToUniversalTime():DateTime.SpecifyKind(value,DateTimeKind.Utc)
            :null;
        DateTime created=Stamp("created_at")??now;
        DateTime? contacted=Stamp("last_contacted_at");
        DateTime? followUp=Stamp("follow_up");
        DateTime lastActivity=DateTimeOffset.TryParse(row["last_activity_text"] as string,CultureInfo.InvariantCulture,
            DateTimeStyles.AssumeUniversal,out var activity)?activity.UtcDateTime:contacted??created;
        bool converted=row["is_converted"] is true;
        string status=LeadStore.Text(row,"status");
        bool active=!converted&&status!="Lost";
        DateTime deadline=created.AddHours(policy.SlaHours);
        bool overdue=active&&followUp.HasValue&&followUp.Value<now;
        bool missed=active&&!contacted.HasValue&&now>deadline;
        bool stale=active&&(now-lastActivity).TotalSeconds>=policy.StaleDays*86400;
        string action=converted?"Open linked contact and deal":
            status=="Lost"?"Review loss reason and nurture timing":
            missed?"Contact now. First-response deadline missed.":
            overdue?"Complete the overdue follow-up":
            stale?"Reconnect with this inactive Lead":
            !contacted.HasValue?"Make first contact":
            status=="Qualified"?"Review qualification and convert":"Schedule the next follow-up";
        string follow=overdue?"Overdue":!followUp.HasValue?"Not scheduled":followUp.Value.Date==now.Date?"Due today":"Upcoming";
        return new(active,overdue,missed,stale,deadline,action,follow);
    }
}
