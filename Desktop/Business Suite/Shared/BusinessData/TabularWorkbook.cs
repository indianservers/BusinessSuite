using System.Globalization;
using System.IO.Compression;
using System.Text;
using System.Xml;

namespace Business_Suite;

internal static class TabularWorkbook
{
    private const string SheetNamespace="http://schemas.openxmlformats.org/spreadsheetml/2006/main";

    internal static async Task<int> WriteAsync(Stream output, string sheetName, string[] fields,
        Func<Action<IEnumerable<object?>>, Task> writeRecords, CancellationToken cancellation)
    {
        using var archive=new ZipArchive(output,ZipArchiveMode.Create,leaveOpen:true);
        Add("[Content_Types].xml","""
            <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
              <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
              <Default Extension="xml" ContentType="application/xml"/>
              <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
              <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
              <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
            </Types>
            """);
        Add("_rels/.rels","""
            <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
              <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
            </Relationships>
            """);
        Add("xl/workbook.xml",$"""
            <workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
              xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
              <bookViews><workbookView/></bookViews>
              <sheets><sheet name="{System.Security.SecurityElement.Escape(sheetName)}" sheetId="1" r:id="rId1"/></sheets>
            </workbook>
            """);
        Add("xl/_rels/workbook.xml.rels","""
            <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
              <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
              <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
            </Relationships>
            """);
        Add("xl/styles.xml","""
            <styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
              <fonts count="2">
                <font><sz val="11"/><name val="Calibri"/></font>
                <font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>
              </fonts>
              <fills count="3">
                <fill><patternFill patternType="none"/></fill>
                <fill><patternFill patternType="gray125"/></fill>
                <fill><patternFill patternType="solid"><fgColor rgb="FF334155"/><bgColor indexed="64"/></patternFill></fill>
              </fills>
              <borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
              <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
              <cellXfs count="2">
                <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
                <xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>
              </cellXfs>
              <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
            </styleSheet>
            """);
        using var sheet=archive.CreateEntry("xl/worksheets/sheet1.xml").Open();
        using var xml=XmlWriter.Create(sheet,new XmlWriterSettings {Encoding=new UTF8Encoding(false)});
        xml.WriteStartElement("worksheet",SheetNamespace);
        xml.WriteStartElement("sheetViews",SheetNamespace);
        xml.WriteStartElement("sheetView",SheetNamespace);
        xml.WriteAttributeString("workbookViewId","0");
        xml.WriteStartElement("pane",SheetNamespace);
        xml.WriteAttributeString("ySplit","1");
        xml.WriteAttributeString("topLeftCell","A2");
        xml.WriteAttributeString("activePane","bottomLeft");
        xml.WriteAttributeString("state","frozen");
        xml.WriteEndElement();
        xml.WriteEndElement();
        xml.WriteEndElement();
        xml.WriteStartElement("cols",SheetNamespace);
        for (int index=0;index<fields.Length;index++)
        {
            string column=(index+1).ToString(CultureInfo.InvariantCulture);
            xml.WriteStartElement("col",SheetNamespace);
            xml.WriteAttributeString("min",column);
            xml.WriteAttributeString("max",column);
            xml.WriteAttributeString("width",fields[index] is "notes" or "description"?"50":"25");
            xml.WriteAttributeString("customWidth","1");
            xml.WriteEndElement();
        }
        xml.WriteEndElement();
        xml.WriteStartElement("sheetData",SheetNamespace);
        WriteRow(1, fields);
        int rowNumber=1;
        await writeRecords(values =>
        {
            cancellation.ThrowIfCancellationRequested();
            if (rowNumber == 1048576)
                throw new InvalidOperationException("The export exceeds Excel's worksheet row limit.");
            WriteRow(++rowNumber, values);
        });
        xml.WriteEndElement();
        xml.WriteStartElement("autoFilter",SheetNamespace);
        xml.WriteAttributeString("ref",$"A1:{ColumnName(fields.Length)}{rowNumber}");
        xml.WriteEndElement();
        xml.WriteEndElement();

        return rowNumber - 1;

        void Add(string name,string contents)
        {
            using var writer=new StreamWriter(archive.CreateEntry(name).Open(),new UTF8Encoding(false));
            writer.Write(contents);
        }

        void WriteRow(int index,IEnumerable<object?> values)
        {
            xml.WriteStartElement("row",SheetNamespace);
            xml.WriteAttributeString("r",index.ToString(CultureInfo.InvariantCulture));
            int column=0;
            foreach (var value in values)
            {
                var address=ColumnName(++column)+index.ToString(CultureInfo.InvariantCulture);
                if (value is null)
                    continue;
                xml.WriteStartElement("c",SheetNamespace);
                xml.WriteAttributeString("r",address);
                if (index==1)
                    xml.WriteAttributeString("s","1");
                if (value is decimal amount)
                    xml.WriteElementString("v",SheetNamespace,amount.ToString(CultureInfo.InvariantCulture));
                else if (value is bool flag)
                {
                    xml.WriteAttributeString("t","b");
                    xml.WriteElementString("v",SheetNamespace,flag?"1":"0");
                }
                else
                {
                    xml.WriteAttributeString("t","inlineStr");
                    xml.WriteStartElement("is",SheetNamespace);
                    xml.WriteStartElement("t",SheetNamespace);
                    xml.WriteAttributeString("xml","space",null,"preserve");
                    string text=value is DateTime date?date.ToString("yyyy-MM-dd'T'HH:mm:ss",CultureInfo.InvariantCulture)
                        :Convert.ToString(value,CultureInfo.InvariantCulture)??"";
                    xml.WriteString(CleanText(text));
                    xml.WriteEndElement();
                    xml.WriteEndElement();
                }
                xml.WriteEndElement();
            }
            xml.WriteEndElement();
        }
    }

    private static string ColumnName(int number)
    {
        string result = "";
        while (number > 0)
        {
            number--;
            result = (char)('A' + number % 26) + result;
            number /= 26;
        }
        return result;
    }

    private static string CleanText(string value)
    {
        var result=new StringBuilder();
        for (int i=0;i<value.Length && result.Length<32767;i++)
        {
            char current=value[i];
            if (XmlConvert.IsXmlChar(current))
                result.Append(current);
            else if (char.IsHighSurrogate(current) && i+1<value.Length
                && char.IsLowSurrogate(value[i+1]) && result.Length<32766)
                result.Append(current).Append(value[++i]);
        }
        return result.ToString();
    }
}
