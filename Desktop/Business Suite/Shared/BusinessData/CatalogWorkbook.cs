using System.IO.Compression;
using System.Globalization;
using System.Xml;
using System.Xml.Linq;

namespace Business_Suite;

internal sealed class CatalogWorkbook
{
    private const int MaximumColumns = 150;
    private readonly byte[] file;
    private readonly Dictionary<string, string> sheetParts;
    internal string[] Sheets { get; }

    internal CatalogWorkbook(string path)
    {
        using (var source = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read))
        {
            if (source.Length > 2 * 1024 * 1024)
                throw new ArgumentException("Import files must be at most 2 MB.");
            using var copy = new MemoryStream();
            source.CopyTo(copy);
            file = copy.ToArray();
        }
        using (var zipStream = new MemoryStream(file, writable: false))
        using (var zip = new ZipArchive(zipStream, ZipArchiveMode.Read))
            if (zip.Entries.Count > 2000 || zip.Entries.Any(entry => entry.Length > 60L * 1024 * 1024) ||
                zip.Entries.Sum(entry => entry.Length) > 60L * 1024 * 1024)
                throw new ArgumentException("The expanded workbook is too large. Split it into smaller files.");
        using var stream = new MemoryStream(file, writable: false);
        using var package = new ZipArchive(stream, ZipArchiveMode.Read);
        var book = OpenPart(package, "xl/workbook.xml");
        var relationships = OpenPart(package, "xl/_rels/workbook.xml.rels");
        var targets = relationships.Root!.Elements().Where(entry =>
            ((string?)entry.Attribute("Type"))?.EndsWith("/worksheet", StringComparison.Ordinal) == true &&
            (string?)entry.Attribute("TargetMode") != "External").ToDictionary(
            entry => (string)entry.Attribute("Id")!, entry => Resolve((string)entry.Attribute("Target")!));
        sheetParts = new Dictionary<string, string>(StringComparer.Ordinal);
        var names = new List<string>();
        foreach (var sheet in book.Root!.Descendants().Where(element => element.Name.LocalName == "sheet"))
        {
            var relationship = sheet.Attributes().FirstOrDefault(attribute => attribute.Name.LocalName == "id");
            string? name = (string?)sheet.Attribute("name");
            if (relationship is not null && !string.IsNullOrWhiteSpace(name) && targets.TryGetValue(relationship.Value, out string target))
            {
                sheetParts.Add(name!, target);
                names.Add(name!);
            }
        }
        Sheets = names.ToArray();
        if (Sheets.Length == 0)
            throw new ArgumentException("The workbook has no worksheets.");
    }

    internal CatalogImportTable ReadSheet(string name, int headerRow, CancellationToken cancellation)
    {
        if (headerRow is < 1 or > 50)
            throw new ArgumentException("Choose a header row from 1 to 50.");
        using var stream = new MemoryStream(file, writable: false);
        using var package = new ZipArchive(stream, ZipArchiveMode.Read);
        if (!sheetParts.TryGetValue(name, out var location))
            throw new ArgumentException("Choose a worksheet from the workbook.");
        var selected = OpenPart(package, location);
        string[] shared = package.GetEntry("xl/sharedStrings.xml") is null ? [] :
            OpenPart(package, "xl/sharedStrings.xml").Root!.Elements().Select(ReadText).ToArray();
        var sheetData = selected.Root!.Elements().FirstOrDefault(element => element.Name.LocalName == "sheetData")
            ?? throw new ArgumentException("The selected worksheet contains no data.");
        var rows = new List<string[]>();
        string[]? headers = null;
        int previousRow = 0;
        foreach (var row in sheetData.Elements().Where(element => element.Name.LocalName == "row"))
        {
            cancellation.ThrowIfCancellationRequested();
            int number = int.TryParse((string?)row.Attribute("r"), NumberStyles.None, CultureInfo.InvariantCulture, out int index)
                ? index : previousRow + 1;
            if (number <= previousRow)
                throw new ArgumentException("Worksheet rows must be in ascending order.");
            previousRow = number;
            if (number < headerRow)
                continue;
            if (number > headerRow + 1500)
                throw new ArgumentException("Remove unused rows below the selected header and try again.");
            if (number > headerRow && headers is null)
                break;
            var values = new string[MaximumColumns];
            int lastUsed = -1;
            int column = -1;
            foreach (var cell in row.Elements().Where(element => element.Name.LocalName == "c"))
            {
                column = (string?)cell.Attribute("r") is { } address ? ColumnIndex(address) : column + 1;
                string value = CellValue(cell, shared);
                if (value.Length == 0)
                    continue;
                if (column >= MaximumColumns)
                    throw new ArgumentException($"Row {number} exceeds the {MaximumColumns}-column limit.");
                if (value.Length > 50000)
                    throw new ArgumentException($"Row {number} contains a cell longer than 50,000 characters.");
                values[column] = value;
                lastUsed = Math.Max(lastUsed, column);
            }
            if (number == headerRow)
            {
                headers = values.Take(lastUsed + 1).Select(value => (value ?? "").Trim()).ToArray();
                if (headers.Length == 0 || headers.Any(value => value.Length is 0 or > 200) ||
                    headers.Distinct(StringComparer.OrdinalIgnoreCase).Count() != headers.Length)
                    throw new ArgumentException("Every used column needs a unique header of up to 200 characters.");
                continue;
            }
            if (lastUsed < 0)
                continue;
            if (rows.Count == 500)
                throw new ArgumentException("Import no more than 500 offerings at a time.");
            if (lastUsed >= headers!.Length)
                throw new ArgumentException($"Row {number} contains values without column headings.");
            rows.Add(values.Take(headers.Length).Select(value => value ?? "").ToArray());
        }
        if (headers is null || rows.Count == 0)
            throw new ArgumentException("The selected sheet has no data below that header row.");
        return CatalogImportTable.FromText(headers, rows);
    }

    private static XDocument OpenPart(ZipArchive package, string location)
    {
        var entry = package.GetEntry(location) ?? throw new ArgumentException("The workbook is missing a required XML part.");
        using var stream = entry.Open();
        using var reader = XmlReader.Create(stream, new XmlReaderSettings
        {
            DtdProcessing = DtdProcessing.Prohibit, XmlResolver = null, MaxCharactersInDocument = 60L * 1024 * 1024
        });
        return XDocument.Load(reader);
    }

    private static string Resolve(string target)
    {
        var baseUri = new Uri("https://workbook.invalid/xl/workbook.xml");
        if (!Uri.TryCreate(baseUri, target.Replace('\\', '/'), out var part) ||
            part.Host != baseUri.Host || part.Scheme != baseUri.Scheme ||
            !part.AbsolutePath.StartsWith("/xl/", StringComparison.Ordinal) || part.Query.Length != 0 || part.Fragment.Length != 0)
            throw new ArgumentException("The workbook contains an unsupported worksheet location.");
        return Uri.UnescapeDataString(part.AbsolutePath.TrimStart('/'));
    }

    private static int ColumnIndex(string address)
    {
        int column = 0;
        int i = 0;
        while (i < address.Length && address[i] is >= 'A' and <= 'Z')
        {
            if (i >= 3)
                throw new ArgumentException("The worksheet contains an invalid cell address.");
            column = column * 26 + address[i++] - 'A' + 1;
        }
        if (column == 0 || i == address.Length)
            throw new ArgumentException("The worksheet contains an invalid cell address.");
        return column - 1;
    }

    private static string CellValue(XElement cell, string[] shared)
    {
        var formula = cell.Elements().FirstOrDefault(element => element.Name.LocalName == "f");
        if (formula is not null)
            return "=" + formula.Value;
        string text = cell.Elements().FirstOrDefault(element => element.Name.LocalName == "v")?.Value ?? "";
        return (string?)cell.Attribute("t") switch
        {
            "s" => int.TryParse(text, NumberStyles.None, CultureInfo.InvariantCulture, out int index) &&
                index >= 0 && index < shared.Length ? shared[index] : throw new ArgumentException("The workbook contains an invalid text reference."),
            "inlineStr" => ReadText(cell),
            "b" => text == "1" ? "true" : "false",
            _ => text
        };
    }

    private static string ReadText(XElement element) => string.Concat(element.Descendants()
        .Where(node => node.Name.LocalName == "t" && !node.Ancestors().Any(parent => parent.Name.LocalName == "rPh"))
        .Select(node => node.Value));
}
