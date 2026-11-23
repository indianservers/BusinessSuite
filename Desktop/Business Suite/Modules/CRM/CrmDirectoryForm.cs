using System.Data;
using System.Text;
using Npgsql;

namespace Business_Suite;

public sealed partial class CrmDirectoryForm : Form
{
    private readonly CrmDirectoryKind kind;
    private readonly CancellationTokenSource lifetime = new();
    private bool loading;
    private bool writing;
    private bool loadedArchived;
    private bool hasSnapshot;
    private int page;
    private string loadedSearch = "";
    private string loadedRole = "";
    private long total;

    public CrmDirectoryForm() : this(CrmDirectoryKind.Companies) { }

    internal CrmDirectoryForm(CrmDirectoryKind kind, string? role = null)
    {
        this.kind = kind;
        InitializeComponent();
        roleFilter.SelectedIndex = role is null ? 0 : roleFilter.Items.IndexOf(role);
        if (role is "Customer" or "Vendor")
        {
            titleLabel.Text = role == "Customer" ? "Customers" : "Vendors";
            Text = $"Business Suite | {titleLabel.Text}";
            roleFilter.Visible = false;
        }
        if (kind == CrmDirectoryKind.Contacts)
        {
            titleLabel.Text = "Contacts";
            roleFilter.Visible = false;
            classificationColumn.HeaderText = "Lifecycle stage";
            contextColumn.HeaderText = "Company";
        }
    }

    private async void DirectoryShown(object sender, EventArgs e) => await LoadPageAsync(0);
    private void DirectoryClosed(object sender, FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }

    private async void FiltersChanged(object sender, EventArgs e)
    {
        if (Visible)
            await LoadPageAsync(0);
    }

    private async void RefreshClicked(object sender, EventArgs e) => await LoadPageAsync(page);
    private async void PreviousClicked(object sender, EventArgs e) => await LoadPageAsync(page - 1);
    private async void NextClicked(object sender, EventArgs e) => await LoadPageAsync(page + 1);
    private async void NewClicked(object sender, EventArgs e) => await OpenEditorAsync(null);
    private async void EditClicked(object sender, EventArgs e)
    {
        if (grid.CurrentRow?.DataBoundItem is DataRowView record)
            await OpenEditorAsync(record);
    }

    private async void ArchiveClicked(object sender, EventArgs e) => await ChangeArchiveAsync(true);
    private async void RestoreClicked(object sender, EventArgs e) => await ChangeArchiveAsync(false);
    private void RecordSelectionChanged(object sender, EventArgs e) => UpdateActions();

    internal static CrmRecordKey GetKey(DataRowView record) =>
        new((int)record["id"], (string)record["revision"], record["details_revision"] as int?);

    private async Task OpenEditorAsync(DataRowView? record)
    {
        if (loading || writing || archivedCheck.Checked || loadedArchived || !hasSnapshot ||
            (record is not null && record["can_write"] is not true))
            return;

        using var editor = new CrmRecordEditForm(kind, record, roleFilter.SelectedItem as string);
        if (editor.ShowDialog(this) == DialogResult.OK)
            await LoadPageAsync(page);
    }

    private async Task ChangeArchiveAsync(bool archive)
    {
        if (loading || writing || !hasSnapshot || archive == archivedCheck.Checked ||
            loadedArchived != archivedCheck.Checked || grid.CurrentRow?.DataBoundItem is not DataRowView record ||
            record["can_write"] is not true)
            return;

        string action = archive ? "Archive" : "Restore";
        if (MessageBox.Show(this, $"{action} {record["name"]}?", "Business Suite",
                MessageBoxButtons.YesNo, MessageBoxIcon.Question, MessageBoxDefaultButton.Button2) != DialogResult.Yes)
            return;

        CancellationToken cancellation = lifetime.Token;
        writing = true;
        UpdateActions();
        try
        {
            await CrmDirectoryWrites.ChangeArchiveAsync(kind, GetKey(record), archive, cancellation);
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { return; }
        catch (Exception error) when (error is ArgumentException or InvalidOperationException or NpgsqlException
            or IOException or UnauthorizedAccessException or TimeoutException)
        {
            if (!cancellation.IsCancellationRequested)
                statusLabel.Text = error is InvalidOperationException or ArgumentException
                    ? error.Message : "Could not update the record. Check the local database and try again.";
            return;
        }
        finally
        {
            writing = false;
            if (!cancellation.IsCancellationRequested)
                UpdateActions();
        }

        if (!cancellation.IsCancellationRequested)
            await LoadPageAsync(page);
    }

    private void UpdateActions()
    {
        bool ready = hasSnapshot && !loading && !writing && loadedArchived == archivedCheck.Checked;
        var record = grid.CurrentRow?.DataBoundItem as DataRowView;
        bool selected = ready && record is not null;
        bool writable = selected && record!["can_write"] is true;
        newButton.Enabled = ready && !loadedArchived;
        editButton.Enabled = archiveButton.Enabled = writable && !loadedArchived;
        restoreButton.Enabled = writable && loadedArchived;
        viewButton.Enabled = selected && !loadedArchived;
        exportButton.Enabled = ready && total > 0 && (!loadedArchived || kind == CrmDirectoryKind.Companies);
    }

    private void ViewClicked(object sender, EventArgs e)
    {
        if (!viewButton.Enabled || grid.CurrentRow?.DataBoundItem is not DataRowView record)
            return;

        using var detail = new CrmRecordForm(record, kind);
        detail.ShowDialog(this);
    }

    private async void ExportClicked(object sender, EventArgs e)
    {
        if (!exportButton.Enabled)
            return;

        CancellationToken cancellation = lifetime.Token;
        writing = true;
        UpdateActions();
        try
        {
            CrmDirectoryPage result = await CrmDirectoryRepository.LoadAsync(kind, loadedSearch, loadedRole,
                loadedArchived, 0, cancellation, exporting: true);
            if (cancellation.IsCancellationRequested)
                return;
            if (result.Records.Rows.Count == 0)
            {
                statusLabel.Text = "No matching records to export.";
                return;
            }

            exportDialog.FileName = $"{titleLabel.Text.ToLowerInvariant()}.csv";
            if (exportDialog.ShowDialog(this) != DialogResult.OK)
                return;

            string[] fields = { "name", "classification", "context", "email", "phone_display", "city", "country", "status" };
            string[] headers = { "Name", classificationColumn.HeaderText, contextColumn.HeaderText, "Email", "Phone", "City", "Country", "Status" };
            using var writer = new StreamWriter(exportDialog.FileName, false, new UTF8Encoding(true));
            writer.WriteLine(string.Join(",", headers.Select(CsvCell)));
            foreach (DataRow row in result.Records.Rows)
                writer.WriteLine(string.Join(",", fields.Select(field => CsvCell(Convert.ToString(row[field]) ?? ""))));
            statusLabel.Text = $"Exported {result.Records.Rows.Count:N0} records.";
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch (Exception error) when (error is InvalidOperationException or ArgumentException or IOException or
            UnauthorizedAccessException or NpgsqlException or TimeoutException)
        {
            if (!cancellation.IsCancellationRequested)
                statusLabel.Text = error is InvalidOperationException or ArgumentException ? error.Message
                    : "Could not export records. Check the database connection and destination.";
        }
        finally
        {
            writing = false;
            if (!cancellation.IsCancellationRequested)
                UpdateActions();
        }
    }

    internal static string CsvCell(string value) => CrmCsv.Cell(value);

    private async Task LoadPageAsync(int requestedPage)
    {
        if (loading || writing || requestedPage < 0)
            return;

        CancellationToken cancellation = lifetime.Token;
        bool previousEnabled = previousButton.Enabled;
        bool nextEnabled = nextButton.Enabled;
        loading = true;
        hasSnapshot = false;
        UpdateActions();
        searchButton.Enabled = refreshButton.Enabled = roleFilter.Enabled = archivedCheck.Enabled =
            previousButton.Enabled = nextButton.Enabled = false;
        statusLabel.Text = "Reading records from PostgreSQL…";
        try
        {
            string search = searchBox.Text.Trim();
            string role = roleFilter.SelectedIndex > 0 ? (string)roleFilter.SelectedItem : "";
            bool archived = archivedCheck.Checked;
            CrmDirectoryPage result = await CrmDirectoryRepository.LoadAsync(kind, search, role,
                archived, requestedPage, cancellation);
            if (result.Records.Rows.Count == 0 && requestedPage > 0)
            {
                requestedPage = 0;
                result = await CrmDirectoryRepository.LoadAsync(kind, search, role, archived, 0, cancellation);
            }
            if (cancellation.IsCancellationRequested)
                return;

            grid.DataSource = result.Records;
            hasSnapshot = true;
            loadedArchived = archived;
            loadedSearch = search;
            loadedRole = role;
            total = result.Total;
            page = requestedPage;
            int start = page * CrmDirectoryRepository.PageSize;
            int end = start + result.Records.Rows.Count;
            statusLabel.Text = result.Total == 0 ? "No matching records." :
                $"Showing {start + 1:N0}–{end:N0} of {result.Total:N0} records";
            previousEnabled = page > 0;
            nextEnabled = end < result.Total;
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch (Exception error) when (error is NpgsqlException or ArgumentException or InvalidOperationException
            or TimeoutException or IOException or UnauthorizedAccessException)
        {
            if (!cancellation.IsCancellationRequested)
            {
                grid.DataSource = null;
                previousEnabled = nextEnabled = false;
                statusLabel.Text = error is InvalidOperationException or ArgumentException ? error.Message
                    : "Could not load records. Check PostgreSQL and the Business Suite .env settings.";
            }
        }
        finally
        {
            if (!cancellation.IsCancellationRequested)
            {
                loading = false;
                searchButton.Enabled = refreshButton.Enabled = roleFilter.Enabled = archivedCheck.Enabled = true;
                previousButton.Enabled = previousEnabled;
                nextButton.Enabled = nextEnabled;
                UpdateActions();
            }
        }
    }
}
