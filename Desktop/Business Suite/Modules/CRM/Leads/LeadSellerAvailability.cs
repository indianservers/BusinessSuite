using System.Globalization;
using System.Text.Json.Nodes;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed record LeadSellerAvailability(int OwnerId,bool Enabled,string Timezone,int[] Days,int StartMinute,
    int EndMinute,int? MaxActiveLeads)
{
    internal static LeadSellerAvailability Default(int ownerId) => new(ownerId,true,"Asia/Kolkata",[0,1,2,3,4],540,1080,null);

    internal static int ParseMinute(string value,bool end)
    {
        value=value.Trim();
        if (end && value=="24:00") return 1440;
        if (!DateTime.TryParseExact(value,"HH:mm",CultureInfo.InvariantCulture,DateTimeStyles.None,out var time))
            throw new ArgumentException("Enter working hours as HH:mm. The end may be 24:00.");
        return time.Hour*60+time.Minute;
    }

    internal static string FormatMinute(int minute) => $"{minute/60:00}:{minute%60:00}";
}

internal static partial class LeadStore
{
    private static List<LeadSellerAvailability> ReadSellerAvailability(JsonObject assignment) =>
        assignment["availability"] is JsonArray policies ? policies.OfType<JsonObject>().Select(policy=>new LeadSellerAvailability(
            policy["ownerId"]?.GetValue<int>()??0,policy["enabled"]?.GetValue<bool>()??true,
            policy["timezone"]?.GetValue<string>()??"Asia/Kolkata",
            policy["days"] is JsonArray days?days.Select(day=>day?.GetValue<int>()??-1).ToArray():[0,1,2,3,4,5,6],
            policy["startMinute"]?.GetValue<int>()??0,policy["endMinute"]?.GetValue<int>()??1440,
            policy["maxActiveLeads"]?.GetValue<int>())).ToList() : [];

    private static async Task ValidateSellerAvailabilityAsync(NpgsqlConnection db,NpgsqlTransaction tx,
        HashSet<int> owners,IReadOnlyList<LeadSellerAvailability> availability,CancellationToken cancellation)
    {
        if (availability.Count>100 || availability.Select(policy=>policy.OwnerId).Distinct().Count()!=availability.Count ||
            availability.Any(policy=>!owners.Contains(policy.OwnerId)))
            throw new ArgumentException("Use up to 100 availability policies, one per owner in the pool or on a rule.");
        if (availability.Any(policy=>policy.Days.Any(day=>day is <0 or >6) ||
            policy.Days.Distinct().Count()!=policy.Days.Length || policy.StartMinute is <0 or >=1440 ||
            policy.EndMinute is <=0 or >1440 || policy.StartMinute>=policy.EndMinute ||
            policy.Timezone.Length is <1 or >80 || policy.MaxActiveLeads is <1 or >100000))
            throw new ArgumentException("Choose unique working days, a time zone, an end time after the start time, and a capacity between 1 and 100,000.");
        string[] zones=availability.Select(policy=>policy.Timezone).Distinct(StringComparer.Ordinal).ToArray();
        if (zones.Length==0) return;
        using var validate=Cmd(db,tx,@"SELECT count(DISTINCT name) FROM pg_catalog.pg_timezone_names WHERE name=ANY(@zones)",
            ("zones",NpgsqlDbType.Array|NpgsqlDbType.Text,zones));
        if ((long)(await validate.ExecuteScalarAsync(cancellation))! !=zones.Length)
            throw new ArgumentException("Choose a valid IANA time zone, such as Asia/Kolkata or Europe/London.");
    }
}
