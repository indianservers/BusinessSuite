using System.Data;
using Telerik.WinControls.UI;

namespace Business_Suite;

internal sealed partial class PmsChecklistForm : Form
{
    private readonly PmsProjectRepository? repository;
    private readonly int task;
    private readonly CancellationTokenSource lifetime = new();
    private PmsChecklistList? checklist;
    private bool busy;

    public PmsChecklistForm() => InitializeComponent();

    internal PmsChecklistForm(PmsProjectRepository repository, DataRow taskRow) : this()
    {
        this.repository = repository;
        task = taskRow.Field<int>("id");
        heading.Text = $"{taskRow["task_key"]} · {taskRow["title"]}";
        UpdateActions();
    }

    private DataRow? Selected => (grid.CurrentRow?.DataBoundItem as DataRowView)?.Row;
    private async void ChecklistLoaded(object? sender, EventArgs e) => await RunAsync(() => ReadAsync(null));
    private async void RefreshClicked(object? sender, EventArgs e) => await RunAsync(() => ReadAsync(null));

    private async Task ReadAsync(int? reselect)
    {
        checklist = await repository!.ReadChecklistAsync(task, lifetime.Token);
        if (lifetime.IsCancellationRequested)
            return;
        grid.DataSource = checklist.Rows.DefaultView;
        if (reselect.HasValue)
            grid.CurrentRow = grid.Rows.FirstOrDefault(row =>
                row.DataBoundItem is DataRowView bound && bound.Row.Field<int>("id") == reselect.Value);
        var items = checklist.Rows.Rows;
        var completed = items.Cast<DataRow>().Count(row => row.Field<bool>("is_completed"));
        statusLabel.Text = items.Count == 0 ? "No checklist items." : $"{completed:N0} of {items.Count:N0} completed";
    }

    private void SelectionChanged(object sender, CurrentRowChangedEventArgs e)
    {
        nameInput.Text = Selected?.Field<string>("title") ?? "";
        UpdateActions();
    }

    private void InputChanged(object? sender, EventArgs e) => UpdateActions();
    private async void AddClicked(object? sender, EventArgs e) => await ChangeAsync(PmsChecklistAction.Add, null, newInput.Text);
    private async void RenameClicked(object? sender, EventArgs e) =>
        await ChangeAsync(PmsChecklistAction.Rename, Selected?.Field<int>("id"), nameInput.Text);
    private async void ToggleClicked(object? sender, EventArgs e) =>
        await ChangeAsync(Selected?.Field<bool>("is_completed") == true ? PmsChecklistAction.Reopen : PmsChecklistAction.Complete,
            Selected?.Field<int>("id"));

    private async void DeleteClicked(object? sender, EventArgs e)
    {
        if (Selected is DataRow row && MessageBox.Show(this, $"Delete checklist item {row["title"]}?", "Delete checklist item",
            MessageBoxButtons.YesNo, MessageBoxIcon.Question, MessageBoxDefaultButton.Button2) == DialogResult.Yes)
            await ChangeAsync(PmsChecklistAction.Delete, row.Field<int>("id"));
    }

    private async void UpClicked(object? sender, EventArgs e) => await MoveAsync(-1);
    private async void DownClicked(object? sender, EventArgs e) => await MoveAsync(1);

    private async Task MoveAsync(int direction)
    {
        if (Selected is not DataRow row || checklist is null)
            return;
        var id = row.Field<int>("id");
        var ids = checklist.Rows.Rows.Cast<DataRow>().Select(item => item.Field<int>("id")).ToArray();
        int old = Array.IndexOf(ids, id);
        int next = old + direction;
        if (old < 0 || next < 0 || next >= ids.Length)
            return;
        (ids[old], ids[next]) = (ids[next], ids[old]);
        await ChangeAsync(PmsChecklistAction.Reorder, null, null, ids, id);
    }

    private async Task ChangeAsync(PmsChecklistAction action, int? item, string? title = null, int[]? order = null, int? reselect = null)
    {
        if (repository is null || checklist is null)
            return;
        await RunAsync(async () =>
        {
            await repository.ChangeChecklistAsync(task, checklist.Revision, action, item, title, order, lifetime.Token);
            if (action == PmsChecklistAction.Add)
                newInput.Text = "";
            await ReadAsync(reselect ?? (action == PmsChecklistAction.Delete ? null : item));
        });
    }

    private async Task RunAsync(Func<Task> work)
    {
        if (repository is null || busy)
            return;
        busy = true;
        UpdateActions();
        statusLabel.Text = "Working with the checklist…";
        try { await work(); }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or Npgsql.NpgsqlException or TimeoutException)
        {
            if (!lifetime.IsCancellationRequested)
                statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException
                    ? error.Message : "Could not update the checklist. Check PostgreSQL and retry.";
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
        var selection = Selected;
        bool editing = !busy && checklist?.CanEdit == true && selection is not null;
        newInput.Enabled = !busy && checklist?.CanAdd == true;
        addButton.Enabled = newInput.Enabled && !string.IsNullOrWhiteSpace(newInput.Text);
        nameInput.Enabled = editing;
        renameButton.Enabled = editing && !string.IsNullOrWhiteSpace(nameInput.Text);
        toggleButton.Enabled = editing;
        toggleButton.Text = selection?.Field<bool>("is_completed") == true ? "Reopen" : "Complete";
        deleteButton.Enabled = !busy && checklist?.CanDelete == true && selection is not null;
        int index = checklist?.Rows.Rows.IndexOf(selection) ?? -1;
        upButton.Enabled = editing && index > 0;
        downButton.Enabled = editing && index >= 0 && index < checklist!.Rows.Rows.Count - 1;
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
