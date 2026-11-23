using System.Data;
using System.Text;
using Telerik.WinControls.UI;

namespace Business_Suite;

public sealed partial class ProjectManagementForm : Form
{
    private DesktopDatabaseSettings? settings;
    private PmsProjectRepository? repository;
    private List<PmsWorkspaceChoice> workspaces = new();
    private DataView? projectView;
    private CancellationTokenSource? loadCancellation;
    private bool loadingWorkspaces;
    private bool changedProject;
    private int initialWorkspaceId;

    public ProjectManagementForm()
    {
        InitializeComponent();
        UpdateActions();
    }

    internal ProjectManagementForm(DesktopDatabaseSettings settings, int initialWorkspaceId = 0) : this()
    {
        this.settings = settings;
        this.initialWorkspaceId = initialWorkspaceId;
    }

    private PmsProjectScope Scope => (PmsProjectScope)Math.Max(0, scopeList.SelectedIndex);
    private int WorkspaceId => workspaceList.SelectedValue is int id ? id : 0;
    private DataRow? SelectedProject => (projectGrid.CurrentRow?.DataBoundItem as DataRowView)?.Row;

    private async void ProjectManagementForm_Load(object sender, EventArgs e) => await ReloadAsync(refreshWorkspaces: true);
    private async void refreshButton_Click(object sender, EventArgs e) => await ReloadAsync(refreshWorkspaces: true);

    private async void FilterChanged(object? sender, EventArgs e)
    {
        if (loadingWorkspaces || repository is null)
            return;
        if (sender == searchTextBox)
            FilterSearch();
        else
            await ReloadAsync(refreshWorkspaces: false);
    }

    private void FilterSearch()
    {
        if (projectView is null)
            return;
        var search = new StringBuilder();
        foreach (var character in searchTextBox.Text.Trim())
        {
            if (character is '[' or ']' or '%' or '*')
                search.Append('[').Append(character).Append(']');
            else if (character == '\'')
                search.Append("''");
            else
                search.Append(character);
        }

        projectView.RowFilter = search.Length == 0
            ? ""
            : $"name LIKE '%{search}%' OR project_key LIKE '%{search}%' OR workspace LIKE '%{search}%'";
        statusLabel.Text = projectView.Count == 0 ? "No matching projects." : $"{projectView.Count:N0} projects";
        UpdateActions();
    }

    private async Task ReloadAsync(bool refreshWorkspaces)
    {
        if (settings is null)
        {
            statusLabel.Text = "Open Project Management from the Business Suite workspace.";
            return;
        }

        loadCancellation?.Cancel();
        var request = new CancellationTokenSource();
        loadCancellation = request;
        projectGrid.DataSource = null;
        projectView = null;
        statusLabel.Text = "Loading projects…";
        UpdateActions();
        try
        {
            if (refreshWorkspaces || repository is null)
            {
                var selected = initialWorkspaceId == 0 ? WorkspaceId : initialWorkspaceId;
                var authorized = await PmsProjectRepository.OpenAsync(settings, request.Token);
                var choices = await authorized.ListWorkspacesAsync(request.Token);
                if (request.IsCancellationRequested)
                    return;
                repository = authorized;
                workspaces = choices;
                loadingWorkspaces = true;
                try
                {
                    workspaceList.Items.Clear();
                    workspaceList.Items.Add(new RadListDataItem("All workspaces") { Value = 0 });
                    foreach (var workspace in workspaces)
                        workspaceList.Items.Add(new RadListDataItem(workspace.Name) { Value = workspace.Id });
                    workspaceList.SelectedValue = selected;
                    if (workspaceList.SelectedIndex < 0)
                        workspaceList.SelectedIndex = 0;
                    initialWorkspaceId = 0;
                }
                finally
                {
                    loadingWorkspaces = false;
                }
            }
            var projects = await repository.ListProjectsAsync(WorkspaceId, Scope, request.Token);
            if (request.IsCancellationRequested)
                return;
            projectView = projects.DefaultView;
            projectGrid.DataSource = projectView;
            FilterSearch();
            if (projects.Rows.Count == 0)
                statusLabel.Text = $"No {Scope.ToString().ToLowerInvariant()} projects in this workspace selection.";
        }
        catch (OperationCanceledException) when (request.IsCancellationRequested)
        {
        }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException)
        {
            if (!request.IsCancellationRequested)
            {
                repository = null;
                statusLabel.Text = error.Message;
            }
        }
        catch (Npgsql.NpgsqlException)
        {
            if (!request.IsCancellationRequested)
            {
                repository = null;
                statusLabel.Text = "Could not load projects. Check the PostgreSQL connection, then select Refresh.";
            }
        }
        finally
        {
            if (loadCancellation == request)
            {
                loadCancellation = null;
                if (!IsDisposed)
                    UpdateActions();
            }
            request.Dispose();
        }
    }

    private void UpdateActions()
    {
        var ready = loadCancellation is null && !changedProject && repository is not null && projectView is not null;
        workHoursButton.Enabled = repository is not null && !changedProject && loadCancellation is null;
        var editable = ready && SelectedProject?.Field<bool>("can_edit") == true;
        newButton.Enabled = ready && repository!.CanCreate && workspaces.Any(choice => choice.CanManage);
        newTaskButton.Enabled = ready && SelectedProject?.Field<bool?>("can_create_task") == true;
        editButton.Enabled = editable && Scope != PmsProjectScope.Trash;
        cloneButton.Enabled = editButton.Enabled && repository!.CanCreate;
        bool canBulkEdit=ready && projectView!.Cast<DataRowView>().Any(row=>PmsProjectBulkForm.CanApplyAny(row.Row,Scope));
        bulkButton.Enabled=canBulkEdit || (ready && Scope!=PmsProjectScope.Trash && repository!.CanExport && projectView!.Count>0);
        bulkButton.Text=canBulkEdit ? "Bulk changes" : "Select projects";
        milestonesButton.Enabled = ready && SelectedProject is not null && Scope != PmsProjectScope.Trash;
        scheduleButton.Enabled = risksButton.Enabled = milestonesButton.Enabled;
        archiveButton.Enabled = ready && Scope != PmsProjectScope.Trash && SelectedProject?.Field<bool>("can_archive") == true;
        archiveButton.Text = Scope == PmsProjectScope.Archived ? "Unarchive" : "Archive";
        trashButton.Enabled = ready && SelectedProject?.Field<bool>(
            Scope == PmsProjectScope.Trash ? "can_restore" : "can_trash") == true;
        trashButton.Text = Scope == PmsProjectScope.Trash ? "Restore" : "Move to Trash";
        exportButton.Enabled = ready && repository!.CanExport && projectView!.Count > 0;
    }

    private void ProjectSelectionChanged(object sender, CurrentRowChangedEventArgs e) => UpdateActions();
    private async void BulkClicked(object? sender,EventArgs e)
    {
        if(repository is null || projectView is null || !bulkButton.Enabled) return;
        using var candidates=projectView.Table!.Clone();
        foreach(var row in projectGrid.ChildRows.OfType<GridViewDataRowInfo>())
            if(row.DataBoundItem is DataRowView record)
                candidates.ImportRow(record.Row);
        using var dialog=new PmsProjectBulkForm(repository,Scope,candidates,WorkspaceId);
        dialog.ShowDialog(this);
        if(dialog.Changed)
            await ReloadAsync(refreshWorkspaces:false);
    }
    private void ProjectDoubleClicked(object sender, GridViewCellEventArgs e)
    {
        if (e.Row is GridViewDataRowInfo && editButton.Enabled)
            editButton.PerformClick();
    }

    private async void newButton_Click(object sender, EventArgs e)
    {
        if (repository is null)
            return;
        using var editor = new PmsProjectEditForm(repository, workspaces, WorkspaceId, null, Scope);
        if (editor.ShowDialog(this) == DialogResult.OK)
        {
            if (Scope != PmsProjectScope.Active)
                scopeList.SelectedIndex = (int)PmsProjectScope.Active;
            await ReloadAsync(refreshWorkspaces: false);
        }
    }

    private async void NewTaskClicked(object sender, EventArgs e)
    {
        if (repository is null || SelectedProject is not DataRow project || !newTaskButton.Enabled)
            return;
        using var editor = new PmsTaskEditForm(repository, project.Field<int>("id"), project.Field<string>("name")!);
        if (editor.ShowDialog(this) == DialogResult.OK)
            await ReloadAsync(refreshWorkspaces: false);
    }

    private async void CloneClicked(object sender, EventArgs e)
    {
        if (repository is null || SelectedProject is not DataRow project || !cloneButton.Enabled)
            return;
        using var clone = new PmsProjectCloneForm(repository, project, Scope);
        if (clone.ShowDialog(this) == DialogResult.OK)
        {
            if (Scope != PmsProjectScope.Active)
                scopeList.SelectedIndex = (int)PmsProjectScope.Active;
            await ReloadAsync(refreshWorkspaces: false);
        }
    }

    private async void MilestonesClicked(object sender, EventArgs e)
    {
        if (repository is null || SelectedProject is not DataRow project || !milestonesButton.Enabled)
            return;
        using var milestones = new PmsMilestonesForm(repository, project);
        milestones.ShowDialog(this);
        await ReloadAsync(refreshWorkspaces: false);
    }

    private void WorkHoursClicked(object sender, EventArgs e)
    {
        if (repository is null || !workHoursButton.Enabled)
            return;
        using var workingHours = new PmsPersonalHoursForm(repository);
        workingHours.ShowDialog(this);
    }

    private void ScheduleClicked(object sender, EventArgs e)
    {
        if (repository is null || SelectedProject is not DataRow project || !scheduleButton.Enabled)
            return;
        using var schedule = new PmsScheduleForm(repository, project);
        schedule.ShowDialog(this);
    }

    private void RisksClicked(object sender, EventArgs e)
    {
        if (repository is null || SelectedProject is not DataRow project || !risksButton.Enabled)
            return;
        using var risks = new PmsRisksForm(repository, project);
        risks.ShowDialog(this);
    }

    private async void editButton_Click(object sender, EventArgs e)
    {
        if (repository is null || SelectedProject is not DataRow project)
            return;
        using var editor = new PmsProjectEditForm(repository, workspaces, project.Field<int?>("workspace_id") ?? 0,
            project, Scope);
        if (editor.ShowDialog(this) == DialogResult.OK)
            await ReloadAsync(refreshWorkspaces: false);
    }

    private async void archiveButton_Click(object sender, EventArgs e) =>
        await ApplyAsync(Scope == PmsProjectScope.Archived ? PmsProjectAction.Unarchive : PmsProjectAction.Archive);

    private async void trashButton_Click(object sender, EventArgs e) =>
        await ApplyAsync(Scope == PmsProjectScope.Trash ? PmsProjectAction.Restore : PmsProjectAction.Trash);

    private async Task ApplyAsync(PmsProjectAction action)
    {
        if (repository is null || SelectedProject is not DataRow project || changedProject)
            return;
        var caption = action == PmsProjectAction.Trash ? "Move to Trash" : action.ToString();
        if (MessageBox.Show(this, $"{caption} {project["name"]}?", caption, MessageBoxButtons.YesNo,
                MessageBoxIcon.Question, MessageBoxDefaultButton.Button2) != DialogResult.Yes)
            return;

        changedProject = true;
        UpdateActions();
        try
        {
            await repository.ApplyActionAsync(project.Field<int>("id"), project.Field<string>("revision")!, Scope,
                action, CancellationToken.None);
            await ReloadAsync(refreshWorkspaces: false);
        }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException)
        {
            statusLabel.Text = error.Message;
        }
        catch (Npgsql.NpgsqlException)
        {
            statusLabel.Text = "The project could not be updated. Check the PostgreSQL connection, then select Refresh.";
        }
        finally
        {
            changedProject = false;
            if (!IsDisposed)
                UpdateActions();
        }
    }

    private void exportButton_Click(object sender, EventArgs e)
    {
        if (projectView is null || exportDialog.ShowDialog(this) != DialogResult.OK)
            return;
        try
        {
            PmsGridExport.WriteCsv(projectGrid, exportDialog.FileName);
            statusLabel.Text = "Projects exported.";
        }
        catch (IOException)
        {
            statusLabel.Text = "The export could not be saved. Choose an available file.";
        }
        catch (UnauthorizedAccessException)
        {
            statusLabel.Text = "The export folder does not allow writes.";
        }
    }

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        base.OnFormClosing(e);
        if (changedProject)
            e.Cancel = true;
        if (!e.Cancel)
            loadCancellation?.Cancel();
    }
}
