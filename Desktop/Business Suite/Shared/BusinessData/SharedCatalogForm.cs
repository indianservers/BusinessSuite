using System.Data;
using Npgsql;

namespace Business_Suite;

public sealed partial class SharedCatalogForm : Form
{
    private readonly SharedCatalogRepository? repository;
    private readonly DesktopDatabaseSettings? settings;
    private readonly CancellationTokenSource lifetime = new();
    private bool canEdit;
    private bool canCreate;
    private bool canExport;
    private bool busy;
    private DataRow? pendingOffering;

    public SharedCatalogForm()
    {
        InitializeComponent();
    }

    internal SharedCatalogForm(DesktopDatabaseSettings settings) : this()
    {
        this.settings = settings;
        repository = new SharedCatalogRepository(settings);
    }

    private void categoriesButton_Click(object? sender, EventArgs e)
    {
        if (settings is null)
            return;
        using var dialog = new CatalogCategoriesForm(settings);
        dialog.ShowDialog(this);
        Reload(this, EventArgs.Empty);
    }

    private async void Reload(object? sender, EventArgs e) => await ReloadAsync();

    private async Task ReloadAsync(string? notice = null)
    {
        if (repository is null || busy || pendingOffering is not null)
            return;
        busy = true;
        UpdateControls();
        statusLabel.Text = "Loading products and services…";
        try
        {
            var (table, exportAllowed, editAllowed, createAllowed) =
                await repository.ListAsync(searchBox.Text, archivedCheckBox.Checked, lifetime.Token);
            if (lifetime.IsCancellationRequested)
                return;
            catalogGrid.DataSource = table;
            canExport = exportAllowed;
            canEdit = editAllowed;
            canCreate = createAllowed;
            string countText = table.Rows.Count switch
            {
                0 => "No catalog records match the search.",
                500 => "Showing up to 500 records. Use Search to narrow the list.",
                _ => $"{table.Rows.Count:N0} records"
            };
            statusLabel.Text = notice is null ? countText : $"{notice} {countText}";
        }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or InvalidOperationException
            or UnauthorizedAccessException or System.Text.Json.JsonException)
        {
            if (!lifetime.IsCancellationRequested)
            {
                catalogGrid.DataSource = null;
                canExport = canEdit = canCreate = false;
                statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException
                    ? error.Message : "Could not load the catalog from PostgreSQL.";
            }
        }
        finally
        {
            if (!lifetime.IsCancellationRequested)
            {
                busy = false;
                UpdateControls();
            }
        }
    }

    private async void ExportClicked(object? sender, EventArgs e)
    {
        if (repository is null || !exportButton.Enabled || exportDialog.ShowDialog(this) != DialogResult.OK)
            return;
        busy = true;
        UpdateControls();
        statusLabel.Text = "Exporting active and archived products and services…";
        try
        {
            string path = exportDialog.FileName;
            var cancellation = lifetime.Token;
            int count = exportDialog.FilterIndex switch
            {
                2 => await repository.ExportCsvAsync(path, cancellation),
                3 => await repository.ExportExcelAsync(path, cancellation),
                _ => await repository.ExportJsonAsync(path, cancellation)
            };
            if (!lifetime.IsCancellationRequested)
                statusLabel.Text = $"Exported {count:N0} catalog records.";
        }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is IOException or NpgsqlException or TimeoutException
            or UnauthorizedAccessException or InvalidOperationException or System.Text.Json.JsonException)
        {
            if (!lifetime.IsCancellationRequested)
                statusLabel.Text = error is UnauthorizedAccessException or InvalidOperationException
                    ? error.Message : "Could not save the catalog export. Check PostgreSQL and the destination folder.";
        }
        finally
        {
            if (!lifetime.IsCancellationRequested)
            {
                busy = false;
                UpdateControls();
            }
        }
    }

    private async void ImportClicked(object? sender, EventArgs e)
    {
        if (repository is null || !importButton.Enabled)
            return;
        using var form = new CatalogImportForm(repository);
        form.ShowDialog(this);
        if (form.Imported > 0)
            await ReloadAsync($"Imported {form.Imported:N0} offerings.");
    }

    private DataRow? SelectedOffering => (catalogGrid.CurrentRow?.DataBoundItem as DataRowView)?.Row;

    private void CatalogSelectionChanged(object? sender, EventArgs e) => UpdateControls();

    private void UpdateControls()
    {
        if (searchButton is null || statusLabel is null)
            return;
        bool confirming = pendingOffering is not null;
        bool ready = !busy && !confirming;
        searchButton.Enabled = archivedCheckBox.Enabled = categoriesButton.Enabled = ready;
        searchBox.Enabled = !confirming;
        catalogGrid.Enabled = !confirming;
        exportButton.Enabled = ready && canExport;
        importButton.Enabled = ready && canCreate;
        lifecycleButton.Enabled = ready && canEdit && SelectedOffering is DataRow row && row.IsNull("workspace_id");
        newOfferingButton.Enabled = ready && canCreate;
        editOfferingButton.Enabled = lifecycleButton.Enabled && SelectedOffering?["kind"] is "Product" or "Service";
        lifecycleButton.Text = archivedCheckBox.Checked ? "Restore" : "Archive";
        lifecyclePrompt.Visible = confirmButton.Visible = cancelButton.Visible = confirming;
        statusLabel.Visible = !confirming;
    }

    private async void NewOffering(object? sender, EventArgs e)
    {
        if (newOfferingButton.Enabled)
            await ShowOfferingEditorAsync(null);
    }

    private async void EditOffering(object? sender, EventArgs e)
    {
        if (editOfferingButton.Enabled)
            await ShowOfferingEditorAsync(SelectedOffering);
    }

    private async Task ShowOfferingEditorAsync(DataRow? row)
    {
        if (repository is null)
            return;
        using var dialog = new CatalogOfferingForm(repository, row);
        if (dialog.ShowDialog(this) == DialogResult.OK)
            await ReloadAsync(row is null ? "Offering created." : "Offering updated.");
    }

    private void RequestLifecycle(object? sender, EventArgs e)
    {
        if (!lifecycleButton.Enabled || SelectedOffering is not DataRow row)
            return;
        bool archive = (bool)row["active"];
        pendingOffering = row;
        lifecyclePrompt.Text = archive
            ? $"Archive {row["item_name"]}? Existing links will be kept."
            : $"Restore {row["item_name"]} to active selectors?";
        confirmButton.Text = archive ? "Archive offering" : "Restore offering";
        UpdateControls();
        cancelButton.Focus();
    }

    private void CancelLifecycle(object? sender, EventArgs e)
    {
        pendingOffering = null;
        UpdateControls();
    }

    private async void ConfirmLifecycle(object? sender, EventArgs e)
    {
        if (repository is null || pendingOffering is not DataRow row || busy)
            return;
        pendingOffering = null;
        busy = true;
        UpdateControls();
        bool changed = false;
        bool archive = (bool)row["active"];
        statusLabel.Text = archive ? "Archiving offering…" : "Restoring offering…";
        try
        {
            await repository.SetArchivedAsync((int)row["id"], (string)row["revision"], archive, lifetime.Token);
            changed = true;
        }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or NpgsqlException or TimeoutException)
        {
            if (!lifetime.IsCancellationRequested)
                statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException
                    ? error.Message : "Could not change the offering in PostgreSQL.";
        }
        finally
        {
            if (!lifetime.IsCancellationRequested)
            {
                busy = false;
                UpdateControls();
            }
        }
        if (changed && !lifetime.IsCancellationRequested)
            await ReloadAsync(archive ? "Offering archived." : "Offering restored.");
    }

    private void SharedCatalogForm_FormClosed(object? sender, FormClosedEventArgs e)
    {
        lifetime.Cancel();
        exportDialog.Dispose();
    }
}
