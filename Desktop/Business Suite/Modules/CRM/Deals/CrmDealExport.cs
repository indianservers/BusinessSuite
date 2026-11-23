using System.Data;
using System.Globalization;
using System.Text;
using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

namespace Business_Suite;

internal sealed partial class CrmDealRepository
{
    internal const int ExportLimit=20000;
    private static readonly (string Field,string Label)[] ExportColumns=[
        ("id","ID"),("name","Deal"),("company","Company"),("pipeline","Pipeline"),("stage","Stage"),("owner_user_id","Owner ID"),
        ("currency","Currency"),("amount","Amount"),("probability","Probability"),("expected_revenue","Weighted value"),
        ("expected_close_date","Expected close"),("priority","Priority"),("status","Status"),("next_follow_up_at","Next action")
    ];

    internal async Task<DataTable> ExportRowsAsync(string search,string status,bool archived,CrmDealFilters filter,int[] selected,
        CancellationToken cancellation)
    {
        if (selected.Length>200 || selected.Any(id=>id<=0))
            throw new ArgumentException("Choose up to 200 valid deal rows.");
        var result=await QueryDealsAsync(search,status,archived,0,cancellation,filter,selected);
        return result.Rows;
    }

    private async Task AuditExportAsync(NpgsqlConnection db,NpgsqlTransaction tx,int actor,long total,bool archived,bool selected,
        CancellationToken cancellation)
    {
        string values=JsonSerializer.Serialize(new {count=total,scope=selected?"selected":"filtered",archived,
            columns=ExportColumns.Select(column=>column.Field)});
        using var audit=Query(db,tx,@"INSERT INTO public.audit_logs
            (organization_id,user_id,actor_authenticated,method,module,entity_type,action,description,new_values)
            VALUES (@org,@actor,true,'CRM','crm','deals','EXPORT','Desktop Deal CSV export',@values)",
            ("actor",NpgsqlDbType.Integer,actor),("values",NpgsqlDbType.Text,values));
        await audit.ExecuteNonQueryAsync(cancellation);
    }

    internal static void WriteCsv(Stream destination,DataTable records,CancellationToken cancellation)
    {
        using var writer=new StreamWriter(destination,new UTF8Encoding(true),4096,leaveOpen:true);
        writer.WriteLine(string.Join(",",ExportColumns.Select(c=>CrmCsv.Cell(c.Label))));
        foreach(DataRow row in records.Rows)
        {
            cancellation.ThrowIfCancellationRequested();
            writer.WriteLine(string.Join(",",ExportColumns.Select(column=>Field(row[column.Field],column.Field))));
        }

        static string Field(object value,string field) => value switch
        {
            DBNull=>"",
            DateTime date=>date.ToString(field=="expected_close_date"?"yyyy-MM-dd":"yyyy-MM-dd HH:mm:ss",CultureInfo.InvariantCulture),
            decimal amount=>amount.ToString(CultureInfo.InvariantCulture),
            int number=>number.ToString(CultureInfo.InvariantCulture),
            _=>CrmCsv.Cell(Convert.ToString(value,CultureInfo.InvariantCulture)??"")
        };
    }
}
