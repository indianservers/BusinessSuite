using System.Data;
using Telerik.WinControls.UI;

namespace Business_Suite;

internal sealed partial class PmsSubtasksForm : Form
{
    private readonly PmsProjectRepository? repository;
    private readonly int parent;
    private readonly CancellationTokenSource lifetime = new();
    private PmsSubtaskList? subtasks;
    private bool busy;

    public PmsSubtasksForm() => InitializeComponent();

    internal PmsSubtasksForm(PmsProjectRepository repository, DataRow task) : this()
    {
        this.repository = repository;
        parent = task.Field<int>("id");
        heading.Text = $"{task["task_key"]} · {task["title"]}";
        UpdateActions();
    }

    private DataRow? Selected => (grid.CurrentRow?.DataBoundItem as DataRowView)?.Row;
    private async void SubtasksLoaded(object? sender, EventArgs e) => await RunAsync(() => ReadAsync());
    private async void RefreshClicked(object? sender, EventArgs e) => await RunAsync(() => ReadAsync());
    private void SelectionChanged(object sender, CurrentRowChangedEventArgs e) => UpdateActions();
    private void TitleChanged(object? sender, EventArgs e) => UpdateActions();

    private async Task ReadAsync(int? select = null)
    {
        subtasks = await repository!.ListSubtasksAsync(parent, lifetime.Token);
        grid.DataSource = subtasks.Rows.DefaultView;
        if (select.HasValue)
            grid.CurrentRow = grid.Rows.FirstOrDefault(row =>
                row.DataBoundItem is DataRowView bound && bound.Row.Field<int>("id") == select.Value);
        statusLabel.Text = subtasks.Rows.Rows.Count == 0 ? "No subtasks." : $"Subtasks {subtasks.Rows.Rows.Count:N0}";
    }

    private async void AddClicked(object? sender, EventArgs e) => await RunAsync(async () =>
    {
        var draft = new PmsSubtaskDraft(titleInput.Text, priorityInput.Text,
            dueInput.Checked ? dueInput.Value.Date : (DateTime?)null, inheritInput.Checked);
        int id = await repository!.CreateSubtaskAsync(parent, subtasks!.Revision, draft, lifetime.Token);
        titleInput.Clear();
        await ReadAsync(id);
    });

    private async void EditClicked(object? sender, EventArgs e)
    {
        if (Selected is not DataRow row)
            return;
        using var editor = new PmsTaskEditForm(repository!, row);
        if (editor.ShowDialog(this) == DialogResult.OK)
            await RunAsync(() => ReadAsync(row.Field<int>("id")));
    }

    private async void AssignClicked(object? sender, EventArgs e)
    {
        if (Selected is not DataRow row)
            return;
        using var editor = new PmsTaskAssignmentForm(repository!, row);
        if (editor.ShowDialog(this) == DialogResult.OK)
            await RunAsync(() => ReadAsync(row.Field<int>("id")));
    }

    private async void TrashClicked(object? sender, EventArgs e)
    {
        if (Selected is not DataRow row || MessageBox.Show(this, $"Move {row["task_key"]} to Trash?", "Move subtask to Trash",
            MessageBoxButtons.YesNo, MessageBoxIcon.Question, MessageBoxDefaultButton.Button2) != DialogResult.Yes)
            return;
        await RunAsync(async () =>
        {
            await repository!.ChangeTaskTrashAsync(row.Field<int>("id"), row.Field<string>("revision")!, false, lifetime.Token);
            await ReadAsync();
        });
    }

    private async void UpClicked(object? sender, EventArgs e) => await MoveAsync(-1);
    private async void DownClicked(object? sender, EventArgs e) => await MoveAsync(1);

    private async Task MoveAsync(int direction)
    {
        if (Selected is not DataRow row || subtasks is null)
            return;
        int id = row.Field<int>("id");
        var ids = subtasks.Rows.Rows.Cast<DataRow>().Select(item => item.Field<int>("id")).ToArray();
        int index = Array.IndexOf(ids, id);
        int next = index + direction;
        if (index < 0 || next < 0 || next >= ids.Length)
            return;
        (ids[index], ids[next]) = (ids[next], ids[index]);
        await RunAsync(async () =>
        {
            await repository!.ReorderSubtasksAsync(parent, subtasks.Revision, ids, lifetime.Token);
            await ReadAsync(id);
        });
    }

    private async Task RunAsync(Func<Task> work)
    {
        if (repository is null || busy)
            return;
        busy = true;
        UpdateActions();
        statusLabel.Text = "Working with subtasks…";
        try { await work(); }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or Npgsql.NpgsqlException or TimeoutException)
        {
            if (!lifetime.IsCancellationRequested)
                statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException
                    ? error.Message : "Could not update subtasks. Check PostgreSQL and retry.";
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
        titleInput.Enabled = priorityInput.Enabled = dueInput.Enabled = inheritInput.Enabled = !busy && subtasks?.CanCreate == true;
        addButton.Enabled = titleInput.Enabled && !string.IsNullOrWhiteSpace(titleInput.Text);
        editButton.Enabled = assignButton.Enabled = !busy && subtasks?.CanEdit == true && selection is not null;
        trashButton.Enabled = !busy && subtasks?.CanDelete == true && selection is not null;
        int index = subtasks?.Rows.Rows.IndexOf(selection) ?? -1;
        upButton.Enabled = editButton.Enabled && index > 0;
        downButton.Enabled = editButton.Enabled && index >= 0 && index < subtasks!.Rows.Rows.Count - 1;
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
