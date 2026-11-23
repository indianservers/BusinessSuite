using System.Data;
using System.Globalization;
using System.Text;
using Telerik.WinControls.UI;

namespace Business_Suite;

internal static class PmsGridExport
{
    internal static void WriteCsv(RadGridView grid, string path)
    {
        var columns = grid.Columns.Where(column => column.IsVisible).OrderBy(column => column.Index).ToArray();
        using var writer = new StreamWriter(path, false, new UTF8Encoding(true));
        writer.WriteLine(string.Join(",", columns.Select(column => Escape(column.HeaderText))));
        foreach (var row in grid.ChildRows.OfType<GridViewDataRowInfo>())
            if (row.DataBoundItem is DataRowView record)
                writer.WriteLine(string.Join(",", columns.Select(column =>
                    Escape(Convert.ToString(record[column.FieldName]) ?? ""))));
    }

    internal static string Escape(string value)
    {
        var first = value.TrimStart().FirstOrDefault();
        if (first is '=' or '+' or '-' or '@' || value.StartsWith("\t") || value.StartsWith("\r") || value.StartsWith("\n"))
            value = "'" + value;
        return "\"" + value.Replace("\"", "\"\"") + "\"";
    }

    internal static void WriteSelectedProjects(IEnumerable<DataRow> rows,string path)
    {
        string[] fields=["project_key","name","client_name","owner_name","status","priority","start_date","due_date","progress","health"];
        using var writer=new StreamWriter(path,false,new UTF8Encoding(true));
        writer.WriteLine(string.Join(",",fields.Select(Escape)));
        foreach(var row in rows)
            writer.WriteLine(string.Join(",",fields.Select(field=>Escape(row[field] is DateTime date ?
                date.ToString("yyyy-MM-dd",CultureInfo.InvariantCulture) :
                field=="progress" && row.IsNull(field) ? "0" : Convert.ToString(row[field],CultureInfo.InvariantCulture) ?? ""))));
    }
}
