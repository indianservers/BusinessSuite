using System.Data;
using System.Globalization;
using System.Text.Json;
using FontFamily = System.Windows.Media.FontFamily;
using Telerik.Windows.Documents.Fixed.FormatProviders.Pdf;
using Telerik.Windows.Documents.Fixed.Model;
using Telerik.Windows.Documents.Fixed.Model.Data;
using Telerik.Windows.Documents.Fixed.Model.Editing;
using Telerik.Windows.Documents.Fixed.Model.Fonts;
using Telerik.Windows.Documents.Fixed.Model.ColorSpaces;
using Telerik.Windows.Documents.Fixed.Model.Resources;
using PageSize = System.Windows.Size;

namespace Business_Suite;

internal static class EmployeeSettlementPdf
{
    internal static byte[] RenderPreview(string company, string templateJson, byte[]? logo, byte[]? signature)
    {
        using var header = new DataTable();
        header.Columns.Add("id",typeof(int));
        header.Columns.Add("company_name",typeof(string));
        header.Columns.Add("employee_code",typeof(string));
        header.Columns.Add("employee_name",typeof(string));
        header.Columns.Add("settlement_date",typeof(DateTime));
        header.Columns.Add("last_working_date",typeof(DateTime));
        header.Columns.Add("net_payable",typeof(decimal));
        var sample = header.Rows.Add(0,company,"SAMPLE-001","Sample Employee",DateTime.Today,DateTime.Today,48000m);
        using var lines = new DataTable();
        lines.Columns.Add("line_type",typeof(string));
        lines.Columns.Add("component_name",typeof(string));
        lines.Columns.Add("amount",typeof(decimal));
        lines.Rows.Add("earning","Basic",40000m);
        lines.Rows.Add("earning","Allowance",10000m);
        lines.Rows.Add("deduction","Sample deduction",2000m);
        return Render(sample,lines.Rows.Cast<DataRow>(),templateJson,logo,signature,true);
    }

    internal static byte[] Render(DataRow settlement, IEnumerable<DataRow> components, string templateJson,
        byte[]? logo, byte[]? signature, bool preview = false)
    {
        const double margin = 53;
        const double width = 794;
        const double height = 1123;
        const double content = width - 2 * margin;
        using var options = JsonDocument.Parse(templateJson);
        var template = options.RootElement;
        string Text(string key, string fallback) => template.ValueKind == JsonValueKind.Object &&
            template.TryGetProperty(key,out var value) && value.ValueKind == JsonValueKind.String ? value.GetString() ?? fallback : fallback;
        bool showCode = template.ValueKind != JsonValueKind.Object || !template.TryGetProperty("show_employee_code",out var codeOption)
            || codeOption.ValueKind != JsonValueKind.False;
        string footer = Text("footer","Confidential - employee payslip");
        string layout = Text("layout","standard");
        var headingColor = layout == "professional" ? new RgbColor(30,64,115) : new RgbColor(27,44,65);
        double fontSize = layout == "compact" ? 11 : 13;
        double spacing = layout == "compact" ? 17 : 23;
        using var logoStream = logo is null ? null : new MemoryStream(logo);
        using var signatureStream = signature is null ? null : new MemoryStream(signature);
        var document = new RadFixedDocument();
        var font = new FontFamily("Segoe UI");
        var amounts = CultureInfo.GetCultureInfo("en-IN");
        var lines = components.ToArray();
        FixedContentEditor? editor = null;
        double y = height;
        int page = 0;
        string Number(decimal number) => number.ToString("N2", amounts);
        string Date(DateTime? value) => value?.ToString("dd MMM yyyy", CultureInfo.InvariantCulture) ?? "";

        DrawBrand(logoStream,150);
        Write(settlement.Field<string>("company_name") ?? "", 18, true);
        if (preview)
            Write("SAMPLE PREVIEW · No payment is represented",14,true);
        var identity = showCode ? settlement.Field<string>("employee_code") + " · " : "";
        Write($"Employee  {identity}{settlement.Field<string>("employee_name")}");
        Write($"Settlement date  {Date(settlement.Field<DateTime?>("settlement_date"))}");
        Write($"Last working date  {Date(settlement.Field<DateTime?>("last_working_date") ?? settlement.Field<DateTime?>("settlement_date"))}");
        Write("Currency  INR");
        y += 16;
        WriteComponents("Earnings", "earning");
        y += 10;
        WriteComponents("Deductions", "deduction");
        y += 12;
        Write("Net payable  INR " + Number(settlement.Field<decimal?>("net_payable") ?? 0m), 16, true);
        if (DrawBrand(signatureStream,140))
            Write("Authorized signatory");

        using var output = new MemoryStream();
        new PdfFormatProvider().Export(document, output);
        return output.ToArray();

        void WriteComponents(string label, string type)
        {
            Write(label, 15, true);
            var group = lines.Where(line => line.Field<string>("line_type") == type).ToArray();
            foreach (var line in group)
                Write($"{line.Field<string>("component_name")}    {Number(line.Field<decimal?>("amount") ?? 0m)}");
            Write($"Total {label.ToLowerInvariant()}    {Number(group.Sum(line => line.Field<decimal?>("amount") ?? 0m))}", 13, true);
        }

        bool DrawBrand(Stream? stream,double maxWidth)
        {
            if (stream is null)
                return false;
            var image = new ImageSource(stream);
            double scale = Math.Min(maxWidth / image.Width,50d / image.Height);
            double displayHeight = image.Height * scale;
            EnsureRoom(displayHeight + 9);
            editor!.Position = new SimplePosition();
            editor.Position.Translate(margin,y);
            editor.DrawImage(image,image.Width * scale,displayHeight);
            y += displayHeight + 9;
            return true;
        }

        void Write(string phrase, double? size = null, bool bold = false)
        {
            var block = Build(phrase, size ?? fontSize, bold);
            var measured = block.Measure(new PageSize(content, double.PositiveInfinity));
            double space = Math.Max(spacing, measured.Height + 5);
            EnsureRoom(space);
            Paint(block, y);
            y += space;
        }

        void EnsureRoom(double space)
        {
            if (y + space <= height - margin - 64 && editor is not null)
                return;
            var sheet = document.Pages.AddPage();
            sheet.Size = new PageSize(width, height);
            editor = new FixedContentEditor(sheet);
            string title = preview ? "Full & Final Settlement · Preview" : $"Full & Final Settlement #{settlement.Field<int>("id")}";
            Paint(Build(title, 23, true), margin);
            page++;
            if (footer.Length > 0)
                Paint(Build(footer,9,false),height - margin - 52);
            Paint(Build($"Page {page}", 10, false), height - margin);
            y = margin + 51;
        }

        Block Build(string text, double size, bool bold)
        {
            var block = new Block();
            block.TextProperties.FontSize = size;
            if (bold)
                block.GraphicProperties.FillColor = headingColor;
            if (!block.TextProperties.TrySetFont(font, System.Windows.FontStyles.Normal,
                bold ? System.Windows.FontWeights.Bold : System.Windows.FontWeights.Normal))
                block.TextProperties.Font = bold ? FontsRepository.HelveticaBold : FontsRepository.Helvetica;
            block.InsertText(text);
            return block;
        }

        void Paint(Block block, double top)
        {
            editor!.Position = new SimplePosition();
            editor.Position.Translate(margin, top);
            editor.DrawBlock(block, new PageSize(content, double.PositiveInfinity));
        }
    }
}
