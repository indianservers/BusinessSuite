using System.ComponentModel;
using System.Text.Json;
using System.Xml;

namespace Business_Suite;

public sealed partial class CatalogColumnMappingForm : Form
{
    private sealed record Target(string Key, string Label);
    private sealed class MappingRow(string source, string sample, string field)
    {
        public string Source { get; } = source;
        public string Sample { get; } = sample;
        public string Field { get; set; } = field;
    }

    private readonly SharedCatalogRepository? repository;
    private CatalogImportTable? table;
    private CatalogWorkbook? workbook;
    private readonly BindingList<MappingRow> rows = [];
    internal List<CatalogImportRow>? Preview { get; private set; }

    public CatalogColumnMappingForm()
    {
        InitializeComponent();
        defaultType.SelectedIndex = 0;
    }

    internal CatalogColumnMappingForm(SharedCatalogRepository repository, CatalogImportTable table) : this()
    {
        this.repository = repository;
        BindTable(table);
    }

    internal CatalogColumnMappingForm(SharedCatalogRepository repository, CatalogWorkbook workbook) : this()
    {
        this.repository = repository;
        this.workbook = workbook;
        worksheetPanel.Visible = true;
        sourceColumn.HeaderText = "Worksheet heading";
        instructions.Text = "Choose a worksheet and header row, then match its columns to catalog fields.";
        sheetBox.DataSource = workbook.Sheets;
        LoadSheetClicked(this, EventArgs.Empty);
    }

    private void BindTable(CatalogImportTable input)
    {
        table = input;
        var suggested = input.SuggestDestinations();
        var targets = CatalogImportTable.KnownFields.Select(field => new Target(field,
            field == "code" ? "SKU / Code" : char.ToUpperInvariant(field[0]) + field.Substring(1).Replace('_', ' ')))
            .Prepend(new("", "Skip column")).ToArray();
        destinationColumn.DataSource = targets;
        rows.Clear();
        for (int index = 0; index < input.Headers.Length; index++)
        {
            string sample = input.Sample(index);
            rows.Add(new(input.Headers[index], sample.Substring(0, Math.Min(180, sample.Length)), suggested[index]));
        }
        mappingGrid.DataSource = rows;
        previewButton.Enabled = true;
    }

    private void SheetSelectionChanged(object? sender, EventArgs e)
    {
        if (workbook is null)
            return;
        table = null;
        rows.Clear();
        previewButton.Enabled = false;
        feedback.Text = "Load the selected worksheet to review its columns.";
    }

    private void LoadSheetClicked(object? sender, EventArgs e)
    {
        if (workbook is null || sheetBox.SelectedItem is not string sheet)
            return;
        SheetSelectionChanged(sender, e);
        try
        {
            BindTable(workbook.ReadSheet(sheet, (int)headerBox.Value, default));
            MappingChanged(sender, e);
        }
        catch (Exception error) when (error is ArgumentException or InvalidOperationException or InvalidDataException or XmlException)
        {
            feedback.Text = error.Message;
        }
    }

    private void MappingChanged(object? sender, EventArgs e) =>
        feedback.Text = "Name and SKU / Code are required.";

    private void PreviewClicked(object? sender, EventArgs e)
    {
        if (repository is null || table is null)
            return;
        mappingGrid.EndEdit();
        try
        {
            Preview = repository.PreviewMappedCatalog(table, rows.Select(row => row.Field ?? "").ToArray(),
                defaultType.SelectedIndex == 1 ? "service" : "product", default);
            DialogResult = DialogResult.OK;
            Close();
        }
        catch (Exception error) when (error is ArgumentException or InvalidOperationException or FormatException or JsonException)
        {
            feedback.Text = error.Message;
        }
    }
}
