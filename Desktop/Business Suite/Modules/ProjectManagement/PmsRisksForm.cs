using System.Data;
using Telerik.WinControls.UI;

namespace Business_Suite;

internal sealed partial class PmsRisksForm : Form
{
    private readonly PmsProjectRepository? repository;
    private readonly int project;
    private readonly CancellationTokenSource lifetime = new();
    private PmsRiskList? risks;
    private bool busy;

    public PmsRisksForm() => InitializeComponent();

    internal PmsRisksForm(PmsProjectRepository repository, DataRow selected) : this()
    {
        this.repository = repository;
        project = selected.Field<int>("id");
        heading.Text = selected.Field<string>("name");
        UpdateActions();
    }

    private DataRow? Selected => (grid.CurrentRow?.DataBoundItem as DataRowView)?.Row;

    private async void RisksLoaded(object? sender, EventArgs e) => await RunAsync(ReadAsync);
    private async void RefreshClicked(object? sender, EventArgs e) => await RunAsync(ReadAsync);

    private async Task ReadAsync()
    {
        risks = await repository!.ListRisksAsync(project, lifetime.Token);
        if (lifetime.IsCancellationRequested)
            return;
        grid.DataSource = risks.Rows.DefaultView;
        statusLabel.Text = risks.Rows.Rows.Count == 0 ? "No risks for this project." : $"{risks.Rows.Rows.Count:N0} risks";
    }

    private async void NewClicked(object? sender, EventArgs e) => await EditAsync(null);
    private async void EditClicked(object? sender, EventArgs e)
    {
        if (editButton.Enabled && Selected is DataRow row)
            await EditAsync(row);
    }

    private void EditDoubleClicked(object sender, GridViewCellEventArgs e)
    {
        if (e.Row is GridViewDataRowInfo && editButton.Enabled)
            EditClicked(sender, e);
    }

    private async Task EditAsync(DataRow? row)
    {
        if (repository is null || risks is null || busy)
            return;
        using var editor = new PmsRiskEditForm(repository, project, risks, row);
        if (editor.ShowDialog(this) == DialogResult.OK)
            await RunAsync(ReadAsync);
    }

    private async void DeleteClicked(object? sender, EventArgs e)
    {
        if (repository is null || !deleteButton.Enabled || Selected is not DataRow row)
            return;
        if (MessageBox.Show(this, $"Delete {row["title"]}?", "Delete risk",
                MessageBoxButtons.YesNo, MessageBoxIcon.Question, MessageBoxDefaultButton.Button2) != DialogResult.Yes)
            return;
        await RunAsync(async () =>
        {
            await repository.DeleteRiskAsync(project, row.Field<int>("id"), row.Field<string>("revision")!, lifetime.Token);
            await ReadAsync();
            statusLabel.Text = "Risk deleted.";
        });
    }

    private void SelectionChanged(object sender, CurrentRowChangedEventArgs e) => UpdateActions();

    private async Task RunAsync(Func<Task> action)
    {
        if (repository is null || busy)
            return;
        busy = true;
        UpdateActions();
        statusLabel.Text = "Working with project risks…";
        try { await action(); }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or Npgsql.NpgsqlException or TimeoutException)
        {
            if (!lifetime.IsCancellationRequested)
                statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException
                    ? error.Message : "Could not complete the risk action. Check PostgreSQL and retry.";
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
        newButton.Enabled = !busy && risks?.CanCreate == true;
        editButton.Enabled = !busy && risks?.CanEdit == true && Selected is not null;
        deleteButton.Enabled = !busy && risks?.CanDelete == true && Selected is not null;
        refreshButton.Enabled = closeButton.Enabled = !busy;
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
