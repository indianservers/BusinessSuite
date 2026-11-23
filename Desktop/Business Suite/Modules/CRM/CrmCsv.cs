namespace Business_Suite;

internal static class CrmCsv
{
    internal static string Cell(string value)
    {
        string trimmed=value.TrimStart();
        if ((trimmed.Length>0 && "=+-@".IndexOf(trimmed[0])>=0) || value.StartsWith("\t") || value.StartsWith("\r"))
            value="'"+value;
        return "\"" + value.Replace("\"", "\"\"") + "\"";
    }
}
