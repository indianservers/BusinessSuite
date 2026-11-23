using Telerik.WinControls.UI;

namespace Business_Suite;

internal sealed partial class PmsWorkspacesForm : Form
{
    private readonly DesktopDatabaseSettings? settings;
    private PmsProjectRepository? repository;
    private CancellationTokenSource? loadCancellation;
    private bool saving;

    public PmsWorkspacesForm()
    {
        InitializeComponent();
        UpdateActions();
    }

    internal PmsWorkspacesForm(DesktopDatabaseSettings settings) : this()
    {
        this.settings = settings;
    }

    private PmsWorkspaceChoice? SelectedWorkspace => workspaceGrid.CurrentRow?.DataBoundItem as PmsWorkspaceChoice;

    private async void LoadWorkspacesClicked(object sender, EventArgs e) => await LoadAsync();

    private async Task LoadAsync(int? selectId = null)
    {
        if (settings is null || loadCancellation is not null)
            return;

        using var request = new CancellationTokenSource();
        loadCancellation = request;
        statusLabel.Text = "Loading workspaces…";
        UpdateActions();
        try
        {
            repository = await PmsProjectRepository.OpenAsync(settings, request.Token);
            var workspaces = await repository.ListWorkspacesAsync(request.Token);
            if (request.IsCancellationRequested)
                return;
            workspaceGrid.DataSource = workspaces;
            if (selectId.HasValue)
                workspaceGrid.CurrentRow = workspaceGrid.Rows.FirstOrDefault(row =>
                    row.DataBoundItem is PmsWorkspaceChoice choice && choice.Id == selectId.Value);
            statusLabel.Text = workspaces.Count == 0 ? "No workspaces are available." : $"{workspaces.Count:N0} workspaces";
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
            workspaceGrid.DataSource = null;
            statusLabel.Text = error is Npgsql.NpgsqlException
                ? "Could not load workspaces. Check the PostgreSQL connection, then select Refresh."
                : error.Message;
        }
        finally
        {
            loadCancellation = null;
            if (!IsDisposed)
                UpdateActions();
        }
    }

    private void NewWorkspaceNameChanged(object sender, EventArgs e) => UpdateActions();
    private void WorkspaceSelectionChanged(object sender, CurrentRowChangedEventArgs e) => UpdateActions();

    private void UpdateActions()
    {
        var ready = loadCancellation is null && !saving && repository is not null;
        newWorkspaceName.Enabled = ready && repository!.CanCreateWorkspace;
        createButton.Enabled = newWorkspaceName.Enabled && !string.IsNullOrWhiteSpace(newWorkspaceName.Text);
        openButton.Enabled = ready && SelectedWorkspace is not null;
        membersButton.Enabled = openButton.Enabled;
        myInvitesButton.Enabled = ready;
        recoveryButton.Enabled = ready && repository!.CanOpenWorkspaceRecovery;
        refreshButton.Enabled = loadCancellation is null && !saving;
    }

    private async void CreateWorkspaceClicked(object sender, EventArgs e)
    {
        if (repository is null || saving)
            return;
        saving = true;
        UpdateActions();
        try
        {
            var id = await repository.CreateWorkspaceAsync(newWorkspaceName.Text, CancellationToken.None);
            newWorkspaceName.Text = "";
            await LoadAsync(id);
        }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or Npgsql.NpgsqlException)
        {
            statusLabel.Text = error is Npgsql.NpgsqlException
                ? "The workspace could not be created. Check the PostgreSQL connection and try again."
                : error.Message;
        }
        finally
        {
            saving = false;
            UpdateActions();
        }
    }

    private void WorkspaceDoubleClicked(object sender, GridViewCellEventArgs e)
    {
        if (e.Row is GridViewDataRowInfo && openButton.Enabled)
            OpenWorkspaceClicked(sender, e);
    }

    private void OpenWorkspaceClicked(object sender, EventArgs e)
    {
        if (settings is null || SelectedWorkspace is not PmsWorkspaceChoice workspace)
            return;
        using var projects = new ProjectManagementForm(settings, workspace.Id);
        projects.ShowDialog(this);
    }

    private async void OpenMembersClicked(object sender, EventArgs e)
    {
        if (repository is null || SelectedWorkspace is not PmsWorkspaceChoice workspace)
            return;
        using var members = new PmsWorkspaceMembersForm(repository, workspace);
        members.ShowDialog(this);
        if (members.MembershipChanged)
            await LoadAsync(workspace.Id);
    }

    private async void OpenInvitationsClicked(object sender, EventArgs e)
    {
        if (repository is null)
            return;
        using var invitations = new PmsWorkspaceInvitationsForm(repository);
        if (invitations.ShowDialog(this) == DialogResult.OK && invitations.AcceptedWorkspace.HasValue)
            await LoadAsync(invitations.AcceptedWorkspace);
    }

    private async void OpenRecoveryClicked(object sender, EventArgs e)
    {
        if (repository is null || !recoveryButton.Enabled)
            return;
        using var recovery = new PmsWorkspaceRecoveryForm(repository);
        recovery.ShowDialog(this);
        if (recovery.WorkspacesChanged)
            await LoadAsync();
    }

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        base.OnFormClosing(e);
        if (saving)
            e.Cancel = true;
        if (!e.Cancel)
            loadCancellation?.Cancel();
    }
}
