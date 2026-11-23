using System.Data;
using Telerik.WinControls.UI;

namespace Business_Suite;

internal sealed partial class EmployeeDocumentsForm : Form
{
    private readonly EmployeeAdministrationRepository? repository;
    private readonly int employee;
    private readonly CancellationTokenSource lifetime = new();
    private string? revision;
    private bool writable;
    private bool busy;

    public EmployeeDocumentsForm() => InitializeComponent();

    internal EmployeeDocumentsForm(EmployeeAdministrationRepository repository, DataRow row) : this()
    {
        this.repository = repository;
        employee = row.Field<int>("id");
        heading.Text = $"{row["employee_name"]} · {row["employee_id"]}";
    }

    private DataRow? Selected => (grid.CurrentRow?.DataBoundItem as DataRowView)?.Row;

    private async void DocumentsLoaded(object? sender, EventArgs e) => await RunAsync(() => ReadAsync());
    private async void RefreshClicked(object? sender, EventArgs e) => await RunAsync(() => ReadAsync());
    private void InputChanged(object? sender, EventArgs e) => UpdateActions();

    private void SelectionChanged(object sender, CurrentRowChangedEventArgs e)
    {
        var row = Selected;
        var value = row?.Field<string>("verification_status");
        verified.SelectedItem = verified.Items.FirstOrDefault(item => item.Text == value);
        reviewer.Text = row?.Field<string>("verifier_name") ?? "";
        company.Text = row?.Field<string>("verifier_company") ?? "";
        notes.Text = row?.Field<string>("verification_notes") ?? "";
        UpdateActions();
    }

    private async Task ReadAsync(int? select = null)
    {
        var documents = await repository!.ReadDocumentsAsync(employee, lifetime.Token);
        revision = documents.Revision;
        writable = documents.Writable;
        grid.DataSource = documents.Rows.DefaultView;
        if (select.HasValue)
            grid.CurrentRow = grid.Rows.FirstOrDefault(row =>
                row.DataBoundItem is DataRowView view && view.Row.Field<int>("id") == select.Value);
        status.Text = documents.Rows.Rows.Count == 0 ? "No employee documents." : $"{documents.Rows.Rows.Count:N0} employee documents";
    }

    private async void UploadClicked(object? sender, EventArgs e)
    {
        if (repository is null || revision is null || !upload.Enabled)
            return;
        using var uploader = new EmployeeAttachmentUploadForm(repository, employee, revision);
        if (uploader.ShowDialog(this) == DialogResult.OK)
            await RunAsync(() => ReadAsync(uploader.AddedDocument));
    }

    private async void SaveCopyClicked(object? sender, EventArgs e)
    {
        if (Selected is not DataRow row)
            return;
        await RunAsync(async () =>
        {
            var file = await repository!.ReadEmployeeAttachmentAsync(employee, row.Field<int>("id"), lifetime.Token);
            copyDialog.FileName = file.Name;
            if (copyDialog.ShowDialog(this) != DialogResult.OK)
            {
                status.Text = "Save copy canceled.";
                return;
            }
            using var copy = new FileStream(copyDialog.FileName, FileMode.Create, FileAccess.Write, FileShare.None, 81920, useAsync: true);
            await copy.WriteAsync(file.Content, 0, file.Content.Length, lifetime.Token);
            status.Text = "Document copy saved.";
        });
    }

    private async void SaveClicked(object? sender, EventArgs e)
    {
        if (Selected is not DataRow row)
            return;
        int document = row.Field<int>("id");
        var review = new EmployeeDocumentReview(verified.Text, reviewer.Text, company.Text, notes.Text);
        await RunAsync(async () =>
        {
            await repository!.VerifyDocumentAsync(employee, document, revision!, review, lifetime.Token);
            await ReadAsync(document);
        });
    }

    private async Task RunAsync(Func<Task> action)
    {
        if (repository is null || busy)
            return;
        busy = true;
        UpdateActions();
        status.Text = "Working with employee documents…";
        try { await action(); }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or Npgsql.NpgsqlException or TimeoutException or IOException)
        {
            if (!lifetime.IsCancellationRequested)
                status.Text = error is InvalidOperationException or UnauthorizedAccessException ? error.Message
                    : "Could not update employee documents. Check PostgreSQL and retry.";
        }
        finally
        {
            busy = false;
            if (!lifetime.IsCancellationRequested)
                UpdateActions();
        }
    }

    private void UpdateActions()
    {
        grid.Enabled = refresh.Enabled = close.Enabled = !busy;
        upload.Enabled = !busy && writable && revision is not null;
        saveCopy.Enabled = !busy && Selected is not null;
        editor.Enabled = !busy && writable && revision is not null && Selected is not null;
        save.Enabled = editor.Enabled && verified.SelectedIndex >= 0;
    }

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        base.OnFormClosing(e);
        if (busy)
            e.Cancel = true;
        if (!e.Cancel)
            lifetime.Cancel();
    }
}
