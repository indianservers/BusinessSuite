using System.Globalization;
using System.Text.Json;
using Telerik.Windows.Documents.Fixed.FormatProviders.Pdf;
using Telerik.Windows.Documents.Fixed.Model;
using Telerik.Windows.Documents.Fixed.Model.ColorSpaces;
using Telerik.Windows.Documents.Fixed.Model.Data;
using Telerik.Windows.Documents.Fixed.Model.Editing;
using Telerik.Windows.Documents.Fixed.Model.Fonts;
using FontFamily = System.Windows.Media.FontFamily;
using Size = System.Windows.Size;

namespace Business_Suite;

internal static class SalesInvoicePdf
{
    private const double Width = 794;
    private const double Height = 1123;
    private const double Margin = 56;
    private const double Content = Width - 2 * Margin;
    private static readonly RgbColor Ink = new(27, 44, 65);
    private static readonly RgbColor Accent = new(25, 91, 110);

    internal static byte[] Render(NativeInvoicePdfData data)
    {
        var invoice = data.Details.Invoice;
        string layout = Text(data.Defaults, "invoice_template");
        double fontSize = layout == "compact" ? 10 : 13;
        double lineSpacing = layout switch { "compact" => 19, "detailed" => 30, _ => 24 };
        var numberFormat = CultureInfo.GetCultureInfo(Text(data.Defaults, "number_format") == "en-US" ? "en-US" : "en-IN");
        string company = First(Text(data.Seller, "legal_name"), Text(data.Seller, "name"), "Seller details pending issue");
        string customer = First(Text(data.Buyer, "name"), "Unlinked");
        return RenderDocument($"Invoice {invoice.Number}" + (data.Draft ? " - DRAFT" : ""), fontSize, lineSpacing,
            (Row, EnsureRoom, Space) =>
            {
                Row(company, 17, true);
                Row(Text(data.Seller, "address"));
                Labeled("Seller GSTIN", Text(data.Seller, "gstin"));
                Row($"{CustomerName(data.Terms)}: {customer}", 14, true);
                Row(Text(data.Buyer, "address"));
                Row($"Invoice date: {Date(invoice.IssueDate)}    Due: {Date(invoice.DueDate)}    Currency: {invoice.Currency}");
                Labeled("Subject", Text(data.Defaults, "subject"));
                Labeled("Order", Text(data.Defaults, "order_number"));
                Labeled("Salesperson", Text(data.Defaults, "salesperson_name"));
                Space(12);
                Row("Invoice lines", 15, true);
                foreach (var line in data.Details.Lines)
                {
                    Row(line.Description, fontSize, true);
                    Row($"{line.Quantity.ToString("0.##########", CultureInfo.InvariantCulture)} x {Amount(line.UnitPrice)}" +
                        $"    Discount {Amount(line.Discount)}    Tax {Amount(line.Tax)}    Line total {Amount(line.Total)}");
                }
                EnsureRoom(lineSpacing * (layout == "detailed" ? 4 : 2) + 16);
                Space(12);
                if (layout == "detailed")
                    Row($"Subtotal {Amount(data.Subtotal)}    Discount {Amount(data.Discount)}    Tax {Amount(data.Tax)}");
                Row($"Total {invoice.Currency} {Amount(invoice.Total)}", 16, true);
                Row($"Paid {Amount(data.Paid)}    Outstanding {Amount(data.Balance)}");
                if (data.Defaults.TryGetProperty("bank_details", out var bank) && bank.ValueKind == JsonValueKind.Object)
                {
                    string[] fields = { "bank_name", "branch_name", "account_number_masked", "ifsc" };
                    Labeled("Bank", string.Join(" | ", fields.Select(field => Text(bank, field)).Where(value => value.Length > 0)));
                }
                Labeled("Payment method", Text(data.Defaults, "payment_method"));
                Labeled("Notes", Text(data.Defaults, "customer_notes"));
                Labeled("Terms", Text(data.Defaults, "terms"));

                string Amount(decimal value) => value.ToString("N2", numberFormat);
                string Date(DateTime? date) => date?.ToString(Text(data.Defaults, "date_format") switch
                {
                    "DD/MM/YYYY" => "dd/MM/yyyy",
                    "MM/DD/YYYY" => "MM/dd/yyyy",
                    _ => "yyyy-MM-dd"
                }, CultureInfo.InvariantCulture) ?? "-";

                void Labeled(string label, string value)
                {
                    if (!string.IsNullOrWhiteSpace(value))
                        Row($"{label}: {value}");
                }
            });
    }

    internal delegate void PdfRow(string value, double? size = null, bool bold = false);

    internal static byte[] RenderDocument(string title, double fontSize, double lineSpacing,
        Action<PdfRow, Action<double>, Action<double>> content)
    {
        var document = new RadFixedDocument();
        var font = new FontFamily("Segoe UI");
        FixedContentEditor editor = null!;
        double y = Margin;
        int page = 0;
        AddPage();
        content(Row, EnsureRoom, space => y += space);
        using var output = new MemoryStream();
        new PdfFormatProvider().Export(document, output);
        return output.ToArray();

        void AddPage()
        {
            var sheet = document.Pages.AddPage();
            sheet.Size = new Size(Width, Height);
            editor = new FixedContentEditor(sheet);
            page++;
            y = Margin;
            foreach (string part in Wrap(title, 22, true))
            {
                Paint(Build(part, 22, true, Accent), y);
                y += 31;
            }
            y += 8;
            Paint(Build($"Page {page}", 10, false, Ink), Height - Margin + 12);
        }

        void EnsureRoom(double height)
        {
            if (y + height > Height - Margin)
                AddPage();
        }

        void Row(string value, double? size, bool bold)
        {
            foreach (string row in Wrap(value, size ?? fontSize, bold))
            {
                var block = Build(row, size ?? fontSize, bold, Ink);
                double height = Math.Max(lineSpacing, block.Measure(new Size(Content, double.PositiveInfinity)).Height + 4);
                EnsureRoom(height);
                Paint(block, y);
                y += height;
            }
        }

        IEnumerable<string> Wrap(string value, double size, bool bold)
        {
            foreach (var paragraph in value.Replace("\r", "").Split('\n'))
            {
                string rest = paragraph.Trim();
                while (rest.Length > 0)
                {
                    int lo = 1;
                    int hi = Math.Min(rest.Length, 200);
                    while (lo < hi)
                    {
                        int middle = (lo + hi + 1) / 2;
                        double measured = Build(rest.Substring(0, middle), size, bold, Ink)
                            .Measure(new Size(double.PositiveInfinity, double.PositiveInfinity)).Width;
                        if (measured <= Content)
                            lo = middle;
                        else
                            hi = middle - 1;
                    }
                    int wrap = lo < rest.Length ? rest.LastIndexOf(' ', lo - 1, lo) : lo;
                    if (wrap <= 0)
                        wrap = lo;
                    if (wrap < rest.Length && char.IsHighSurrogate(rest[wrap - 1]))
                        wrap = wrap > 1 ? wrap - 1 : 2;
                    yield return rest.Substring(0, wrap);
                    rest = rest.Substring(wrap).TrimStart();
                }
            }
        }

        void Paint(Block block, double top)
        {
            editor.Position = new SimplePosition();
            editor.Position.Translate(Margin, top);
            editor.DrawBlock(block, new Size(Content, double.PositiveInfinity));
        }

        Block Build(string value, double size, bool bold, RgbColor color)
        {
            var block = new Block();
            block.TextProperties.FontSize = size;
            block.GraphicProperties.FillColor = color;
            if (!block.TextProperties.TrySetFont(font, System.Windows.FontStyles.Normal,
                bold ? System.Windows.FontWeights.Bold : System.Windows.FontWeights.Normal))
                block.TextProperties.Font = bold ? FontsRepository.HelveticaBold : FontsRepository.Helvetica;
            block.InsertText(value);
            return block;
        }
    }

    private static string CustomerName(JsonElement terms) =>
        terms.ValueKind == JsonValueKind.Object && terms.TryGetProperty("customer", out var names) &&
        names.ValueKind == JsonValueKind.Array && names.GetArrayLength() > 0 && names[0].ValueKind == JsonValueKind.String
            ? First(names[0].GetString() ?? "", "Customer")
            : "Customer";

    private static string Text(JsonElement obj, string key) =>
        obj.ValueKind == JsonValueKind.Object && obj.TryGetProperty(key, out var value) &&
        value.ValueKind == JsonValueKind.String ? value.GetString() ?? "" : "";

    private static string First(params string[] values) => values.First(value => !string.IsNullOrWhiteSpace(value));
}
