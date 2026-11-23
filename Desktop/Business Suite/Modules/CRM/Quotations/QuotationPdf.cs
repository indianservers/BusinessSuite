using System.Globalization;
using Telerik.Windows.Documents.Fixed.FormatProviders.Pdf;
using Telerik.Windows.Documents.Fixed.Model;
using Telerik.Windows.Documents.Fixed.Model.Editing;
using Telerik.Windows.Documents.Fixed.Model.Fonts;
using Telerik.Windows.Documents.Fixed.Model.ColorSpaces;
using FontFamily = System.Windows.Media.FontFamily;
using Telerik.Windows.Documents.Fixed.Model.Data;
using Size = System.Windows.Size;
using Rect = System.Windows.Rect;

namespace Business_Suite;

internal sealed record QuotationPdfData(int Id,int Version,string Number,string Status,DateTime Issue,DateTime Expiry,
    string Currency,string Seller,string SellerAddress,string SellerContact,string SellerTax,string Customer,
    string CustomerAddress,string CustomerContact,string Terms,List<QuoteDraftLine> Lines,bool Draft);

internal static class QuotationPdf
{
    private const double Width=794;
    private const double Height=1123;
    private const double Gutter=46;
    private const double Content=Width-2*Gutter;
    private static readonly RgbColor Ink=new(27,44,65);
    private static readonly RgbColor Muted=new(74,91,110);
    private static readonly RgbColor Accent=new(25,91,110);
    private static readonly RgbColor Pale=new(231,240,244);

    internal static byte[] Render(QuotationPdfData data)
    {
        var document=new RadFixedDocument();
        FixedContentEditor editor=null!;
        double y=0;
        int page=0;
        var font=new FontFamily("Segoe UI");
        AddPage();
        Paragraph(data.Seller,17,true);
        Paragraph(data.SellerAddress);
        Paragraph(data.SellerContact);
        Paragraph(data.SellerTax);
        y+=17;
        Paragraph("Bill to",12,true);
        Paragraph(data.Customer,14,true);
        Paragraph(data.CustomerAddress);
        Paragraph(data.CustomerContact);
        y+=10;
        Paragraph($"Issue date {data.Issue:dd MMM yyyy}        Valid until {data.Expiry:dd MMM yyyy}        Currency {data.Currency}",11);
        y+=18;
        DrawColumns();
        var amountRows=new List<QuoteLineTotals>();
        foreach (var line in data.Lines)
        {
            var amount=QuoteDraftRepository.Calculate(line);
            amountRows.Add(amount);
            var text=Build(line.Name,11,false,Ink);
            double lineHeight=Math.Max(27,text.Measure(new Size(252,double.PositiveInfinity)).Height+12);
            if (EnsureRoom(lineHeight))
                DrawColumns();
            Paint(text,Gutter+8,y+5,252);
            Paint(Build(line.Quantity.ToString("0.##",CultureInfo.InvariantCulture),10,false,Ink),Gutter+270,y+6,53);
            Paint(Build(Display(line.UnitPrice),10,false,Ink),Gutter+326,y+6,95);
            Paint(Build(Display(amount.Discount),10,false,Ink),Gutter+424,y+6,90);
            Paint(Build(Display(amount.Tax),10,false,Ink),Gutter+517,y+6,80);
            Paint(Build(Display(amount.Total),10,true,Ink),Gutter+601,y+6,95);
            y+=lineHeight;
            Rule(Pale,1);
        }
        if (data.Lines.Count==0)
            Paragraph("No quotation lines recorded.");
        y+=18;
        EnsureRoom(120);
        Amount("Subtotal",amountRows.Sum(amount=>amount.Gross));
        Amount("Discount",amountRows.Sum(amount=>amount.Discount));
        Amount("Tax",amountRows.Sum(amount=>amount.Tax));
        Amount("Total",amountRows.Sum(amount=>amount.Total),true);
        y+=18;
        Paragraph("Terms and conditions",14,true);
        string terms=string.IsNullOrWhiteSpace(data.Terms)
            ?"Standard commercial terms apply unless otherwise agreed in writing.":data.Terms;
        foreach(var part in SplitText(terms))
            Paragraph(part);

        using var output=new MemoryStream();
        new PdfFormatProvider().Export(document,output);
        return output.ToArray();

        void AddPage()
        {
            var sheet=document.Pages.AddPage();
            sheet.Size=new Size(Width,Height);
            editor=new FixedContentEditor(sheet);
            editor.GraphicProperties.IsStroked=false;
            editor.GraphicProperties.IsFilled=true;
            page++;
            y=Gutter;
            Paint(Build(data.Draft?"QUOTATION · DRAFT":"QUOTATION",22,true,Accent),Gutter,y,Content);
            Paint(Build($"Page {page}",10,false,Muted),Width-Gutter-58,Height-Gutter+5,58);
            y+=36;
            Paint(Build($"{data.Number}  /  Version {data.Version}  /  {data.Status}",11,false,Muted),Gutter,y,Content);
            y+=30;
            Rule(Accent,2);
            y+=18;
        }
        bool EnsureRoom(double height)
        {
            if (y+height<=Height-Gutter-20)
                return false;
            AddPage();
            return true;
        }
        void Paragraph(string value,double fontSize=11,bool bold=false)
        {
            if (value.Length==0)return;
            foreach (string part in SplitText(value))
            {
                var block=Build(part,fontSize,bold,Ink);
                double measured=block.Measure(new Size(Content,double.PositiveInfinity)).Height+5;
                EnsureRoom(measured);
                Paint(block,Gutter,y,Content);
                y+=measured;
            }
        }
        void DrawColumns()
        {
            EnsureRoom(30);
            editor.Position=new SimplePosition();
            editor.Position.Translate(Gutter,y);
            editor.GraphicProperties.FillColor=Pale;
            editor.DrawRectangle(new Rect(0,0,Content,27));
            Paint(Build("Product or service",10,true,Ink),Gutter+8,y+7,252);
            Paint(Build("Qty",10,true,Ink),Gutter+270,y+7,53);
            Paint(Build("Unit price",10,true,Ink),Gutter+326,y+7,95);
            Paint(Build("Discount",10,true,Ink),Gutter+424,y+7,90);
            Paint(Build("Tax",10,true,Ink),Gutter+517,y+7,80);
            Paint(Build("Total",10,true,Ink),Gutter+601,y+7,95);
            y+=30;
        }
        void Amount(string label,decimal amount,bool bold=false)
        {
            Paint(Build(label,11,bold,Ink),Width-Gutter-245,y,125);
            Paint(Build($"{data.Currency} {Display(amount)}",11,bold,Ink),Width-Gutter-120,y,120);
            y+=23;
        }
        void Rule(RgbColor color,double height)
        {
            editor.Position=new SimplePosition();
            editor.Position.Translate(Gutter,y);
            editor.GraphicProperties.FillColor=color;
            editor.DrawRectangle(new Rect(0,0,Content,height));
        }
        void Paint(Block block,double x,double top,double width)
        {
            editor.Position=new SimplePosition();
            editor.Position.Translate(x,top);
            editor.DrawBlock(block,new Size(width,double.PositiveInfinity));
        }
        Block Build(string value,double size,bool bold,RgbColor color)
        {
            var block=new Block();
            block.TextProperties.FontSize=size;
            block.GraphicProperties.FillColor=color;
            if (!block.TextProperties.TrySetFont(font,System.Windows.FontStyles.Normal,
                    bold?System.Windows.FontWeights.Bold:System.Windows.FontWeights.Normal))
                block.TextProperties.Font=bold?FontsRepository.HelveticaBold:FontsRepository.Helvetica;
            block.InsertText(value);
            return block;
        }
    }

    private static string Display(decimal value)=>value.ToString("N2",CultureInfo.InvariantCulture);

    private static IEnumerable<string> SplitText(string value)
    {
        foreach (string line in value.Replace("\r","").Split('\n'))
        {
            int start=0;
            while (line.Length-start>450)
            {
                int split=line.LastIndexOf(' ',start+450,450);
                if (split<=start) split=start+450;
                yield return line.Substring(start,split-start);
                start=split;
            }
            if (start<line.Length)
                yield return line.Substring(start);
        }
    }
}
