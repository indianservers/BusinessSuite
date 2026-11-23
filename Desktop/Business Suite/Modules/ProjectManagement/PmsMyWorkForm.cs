using System.Data;
using Telerik.WinControls.UI;

namespace Business_Suite;

internal sealed partial class PmsMyWorkForm : Form
{
    private readonly DesktopDatabaseSettings? settings;
    private PmsProjectRepository? repository;
    private CancellationTokenSource? loadCancellation;
    private bool bindingWorkspaces;
    private bool changingTrash;

    public PmsMyWorkForm()
    {
        InitializeComponent();
        trashButton.Enabled = assignButton.Enabled = editButton.Enabled = exportButton.Enabled = false;
    }

    internal PmsMyWorkForm(DesktopDatabaseSettings settings) : this()
    {
        this.settings = settings;
    }

    private async void MyWorkLoaded(object sender, EventArgs e) => await ReloadAsync(refreshWorkspaces: true);
    private async void RefreshClicked(object sender, EventArgs e) => await ReloadAsync(refreshWorkspaces: true);

    private async void ViewChanged(object sender, EventArgs e)
    {
        if (!bindingWorkspaces && repository is not null)
            await ReloadAsync(refreshWorkspaces: false);
    }

    private async void SearchKeyDown(object sender, KeyEventArgs e)
    {
        if (e.KeyCode != Keys.Enter)
            return;
        e.SuppressKeyPress = true;
        await ReloadAsync(refreshWorkspaces: false);
    }

    private int WorkspaceId => workspaceList.SelectedValue is int id ? id : 0;
    private DataRow? SelectedTask => (taskGrid.CurrentRow?.DataBoundItem as DataRowView)?.Row;
    private bool ShowingTrash => Equals(viewList.SelectedValue, "trash");

    private async Task ReloadAsync(bool refreshWorkspaces)
    {
        if (settings is null)
            return;
        loadCancellation?.Cancel();
        using var request = new CancellationTokenSource();
        loadCancellation = request;
        taskGrid.DataSource = null;
        descriptionTextBox.Text = "";
        statusLabel.Text = "Loading tasks…";
        trashButton.Enabled = assignButton.Enabled = editButton.Enabled = exportButton.Enabled = false;
        try
        {
            if (refreshWorkspaces || repository is null)
            {
                var selected = WorkspaceId;
                var authorized = await PmsProjectRepository.OpenAsync(settings, request.Token);
                var workspaces = await authorized.ListWorkspacesAsync(request.Token);
                if (request.IsCancellationRequested)
                    return;
                repository = authorized;
                bindingWorkspaces = true;
                try
                {
                    workspaceList.Items.Clear();
                    workspaceList.Items.Add(new RadListDataItem("All workspaces") { Value = 0 });
                    foreach (var workspace in workspaces)
                        workspaceList.Items.Add(new RadListDataItem(workspace.Name) { Value = workspace.Id });
                    workspaceList.SelectedValue = selected;
                    if (workspaceList.SelectedIndex < 0)
                        workspaceList.SelectedIndex = 0;
                }
                finally
                {
                    bindingWorkspaces = false;
                }
            }

            var rows = await repository.ListWorkAsync(viewList.SelectedValue as string ?? "mine", searchTextBox.Text,
                overdueCheckBox.Checked, WorkspaceId, request.Token);
            if (request.IsCancellationRequested)
                return;
            taskGrid.DataSource = rows.DefaultView;
            deletedColumn.IsVisible = ShowingTrash;
            overdueCheckBox.Enabled = !ShowingTrash;
            statusLabel.Text = rows.Rows.Count == 0 ? "No tasks match these filters." : $"{rows.Rows.Count:N0} tasks";
            exportButton.Enabled = repository.CanExport && rows.Rows.Count > 0;
        }
        catch (OperationCanceledException) when (request.IsCancellationRequested)
        {
        }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or Npgsql.NpgsqlException)
        {
            if (request.IsCancellationRequested)
                return;
            repository = null;
            statusLabel.Text = error is Npgsql.NpgsqlException
                ? "Could not load tasks. Check the PostgreSQL connection, then apply filters again."
                : error.Message;
        }
        finally
        {
            if (loadCancellation == request)
            {
                loadCancellation = null;
                if (!IsDisposed)
                    UpdateSelection();
            }
        }
    }

    private void TaskSelectionChanged(object sender, CurrentRowChangedEventArgs e) => UpdateSelection();

    private void UpdateSelection()
    {
        descriptionTextBox.Text = SelectedTask?.Field<string>("description") ?? "";
        bool ready = loadCancellation is null && !changingTrash && repository is not null;
        editButton.Enabled = ready && SelectedTask?.Field<bool?>("can_edit") == true;
        assignButton.Enabled = editButton.Enabled;
        dependenciesButton.Enabled = subtasksButton.Enabled = ready && !ShowingTrash && SelectedTask is not null;
        checklistButton.Enabled = ready && !ShowingTrash && SelectedTask is not null;
        trashButton.Enabled = ready && SelectedTask?.Field<bool?>("can_change_trash") == true;
        trashButton.Text = ShowingTrash ? "Restore" : "Move to Trash";
    }

    private void TaskDoubleClicked(object sender, GridViewCellEventArgs e)
    {
        if (e.Row is GridViewDataRowInfo && editButton.Enabled)
            EditTaskClicked(sender, e);
    }

    private async void EditTaskClicked(object sender, EventArgs e)
    {
        if (repository is null || SelectedTask is not DataRow task || !editButton.Enabled)
            return;
        using var editor = new PmsTaskEditForm(repository, task);
        if (editor.ShowDialog(this) == DialogResult.OK)
            await ReloadAsync(refreshWorkspaces: false);
    }

    private async void AssignTaskClicked(object sender, EventArgs e)
    {
        if (repository is null || SelectedTask is not DataRow task || !assignButton.Enabled)
            return;
        using var editor = new PmsTaskAssignmentForm(repository, task);
        if (editor.ShowDialog(this) == DialogResult.OK)
            await ReloadAsync(refreshWorkspaces: false);
    }

    private async void OpenDependenciesClicked(object? sender, EventArgs e)
    {
        if (repository is null || SelectedTask is not DataRow task || !dependenciesButton.Enabled)
            return;
        using var editor = new PmsDependenciesForm(repository, task);
        editor.ShowDialog(this);
        await ReloadAsync(refreshWorkspaces: false);
    }

    private async void OpenSubtasksClicked(object sender, EventArgs e)
    {
        if (repository is null || SelectedTask is not DataRow task || !subtasksButton.Enabled)
            return;
        using var editor = new PmsSubtasksForm(repository, task);
        editor.ShowDialog(this);
        await ReloadAsync(refreshWorkspaces: false);
    }

    private void OpenChecklistClicked(object sender, EventArgs e)
    {
        if (repository is null || SelectedTask is not DataRow task || !checklistButton.Enabled)
            return;
        using var checklist = new PmsChecklistForm(repository, task);
        checklist.ShowDialog(this);
    }

    private async void TrashTaskClicked(object sender, EventArgs e)
    {
        if (repository is null || SelectedTask is not DataRow task || !trashButton.Enabled)
            return;
        bool restore = ShowingTrash;
        if (!restore && MessageBox.Show(this, $"Move {task["task_key"]} to Trash?", "Move to Trash",
                MessageBoxButtons.YesNo, MessageBoxIcon.Question, MessageBoxDefaultButton.Button2) != DialogResult.Yes)
            return;
        changingTrash = true;
        UpdateSelection();
        try
        {
            await repository.ChangeTaskTrashAsync(task.Field<int>("id"), task.Field<string>("revision")!, restore,
                CancellationToken.None);
            await ReloadAsync(refreshWorkspaces: false);
        }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or Npgsql.NpgsqlException or TimeoutException)
        {
            statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException
                ? error.Message : "Could not update task Trash. Check PostgreSQL and try again.";
        }
        finally
        {
            changingTrash = false;
            UpdateSelection();
        }
    }

    private void ExportClicked(object sender, EventArgs e)
    {
        if (exportDialog.ShowDialog(this) != DialogResult.OK)
            return;
        try
        {
            PmsGridExport.WriteCsv(taskGrid, exportDialog.FileName);
            statusLabel.Text = "Tasks exported.";
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException)
        {
            statusLabel.Text = "The export could not be saved. Choose an available file.";
        }
    }

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        base.OnFormClosing(e);
        if (changingTrash)
            e.Cancel = true;
        if (!e.Cancel)
            loadCancellation?.Cancel();
    }
}
