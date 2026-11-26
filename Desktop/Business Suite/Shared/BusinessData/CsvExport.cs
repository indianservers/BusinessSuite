namespace Business_Suite;

internal static class CsvExport
{
    internal static string Escape(string value) => "\"" + (value ?? "").Replace("\"", "\"\"") + "\"";
}
