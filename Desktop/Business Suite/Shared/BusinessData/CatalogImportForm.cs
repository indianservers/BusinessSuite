using System.Text;
using System.Text.Json;
using System.Xml;
using Microsoft.VisualBasic.FileIO;
using Npgsql;

namespace Business_Suite;

public sealed partial class CatalogImportForm : Form
{
    private readonly SharedCatalogRepository? repository;
    private List<CatalogImportRow>? pending;
    private bool busy;
    internal int Imported { get; private set; }

    public CatalogImportForm() => InitializeComponent();
    internal CatalogImportForm(SharedCatalogRepository repository) : this() => this.repository = repository;

    private void BrowseClicked(object? sender, EventArgs e)
    {
        if (repository is null || busy || picker.ShowDialog(this) != DialogResult.OK)
            return;
        PreviewFile(picker.FileName);
    }

    private void PreviewFile(string path)
    {
        pending = null;
        grid.DataSource = null;
        importButton.Enabled = false;
        fileLabel.Text = Path.GetFileName(path);
        try
        {
            string extension = Path.GetExtension(path).ToLowerInvariant();
            using var mapping = extension switch
            {
                ".xlsx" => new CatalogColumnMappingForm(repository!, new CatalogWorkbook(path)),
                ".json" => new CatalogColumnMappingForm(repository!,
                    CatalogImportTable.ReadJson(SharedCatalogRepository.ReadImportText(path), default)),
                ".csv" or ".tsv" => new CatalogColumnMappingForm(repository!,
                    CatalogImportTable.Read(SharedCatalogRepository.ReadImportText(path), default, extension == ".tsv" ? "\t" : ",")),
                _ => throw new ArgumentException("Choose an Excel, JSON, CSV or TSV catalog file.")
            };
            if (mapping.ShowDialog(this) != DialogResult.OK || mapping.Preview is null)
            {
                feedback.Text = "Column mapping was cancelled.";
                return;
            }
            pending = mapping.Preview;
            grid.DataSource = pending.Select(row => new
            {
                row.Offering.Kind, row.Offering.Name, row.Offering.Code, row.Offering.Price,
                row.Offering.Currency, Status = row.Active ? "Active" : "Archived"
            }).ToList();
            feedback.Text = $"{pending.Count:N0} offerings ready. Import creates new records in the selected branch.";
            importButton.Enabled = true;
        }
        catch (Exception error) when (error is IOException or ArgumentException or JsonException or FormatException or
            MalformedLineException or UnauthorizedAccessException or InvalidOperationException or InvalidDataException or XmlException)
        {
            feedback.Text = error is DecoderFallbackException ? "The catalog file is not valid UTF-8." : error.Message;
        }
    }

    private async void ImportClicked(object? sender, EventArgs e)
    {
        if (pending is null || repository is null || busy)
            return;
        busy = true;
        browseButton.Enabled = importButton.Enabled = closeButton.Enabled = false;
        feedback.Text = "Saving the catalog batch…";
        try
        {
            Imported = await repository.ImportCatalogRowsAsync(pending, default);
            DialogResult = DialogResult.OK;
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or InvalidOperationException or
            UnauthorizedAccessException or ArgumentException)
        {
            feedback.Text = error is NpgsqlException or TimeoutException
                ? "The batch outcome could not be confirmed. Refresh the catalog before retrying." : error.Message;
        }
        finally
        {
            busy = false;
            browseButton.Enabled = closeButton.Enabled = true;
            importButton.Enabled = Imported == 0;
            if (Imported > 0)
                Close();
        }
    }

    private void ClosingImport(object? sender, FormClosingEventArgs e) => e.Cancel = busy;
}
