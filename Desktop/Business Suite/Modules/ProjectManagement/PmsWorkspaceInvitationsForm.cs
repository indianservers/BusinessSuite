using System.Data;
using Telerik.WinControls.UI;

namespace Business_Suite;

internal sealed partial class PmsWorkspaceInvitationsForm : Form
{
    private readonly PmsProjectRepository? repository;
    private readonly int? workspace;
    private readonly CancellationTokenSource lifetime = new();
    private bool busy;
    private bool canIssue;
    private bool canRevoke;

    public PmsWorkspaceInvitationsForm() => InitializeComponent();

    internal PmsWorkspaceInvitationsForm(PmsProjectRepository repository, PmsWorkspaceChoice? choice = null) : this()
    {
        this.repository = repository;
        workspace = choice?.Id;
        heading.Text = choice is null ? "My invitations" : $"Invitations · {choice.Name}";
        emailInput.Visible = roleInput.Visible = issueButton.Visible = resendButton.Visible = revokeButton.Visible = workspace.HasValue;
        acceptButton.Visible = !workspace.HasValue;
        UpdateActions();
    }

    internal int? AcceptedWorkspace { get; private set; }
    private DataRow? Selected => (invitationGrid.CurrentRow?.DataBoundItem as DataRowView)?.Row;

    private async void InvitationsLoaded(object? sender, EventArgs e) => await RunAsync(ReadAsync);

    private async Task ReadAsync()
    {
        var result = await repository!.ReadInvitationsAsync(workspace, lifetime.Token);
        if (lifetime.IsCancellationRequested)
            return;
        canIssue = result.CanIssue;
        canRevoke = result.CanRevoke;
        roleInput.Items[2].Enabled = result.CanInviteAdmin;
        invitationGrid.DataSource = result.Records.DefaultView;
        statusLabel.Text = workspace.HasValue
            ? "Signed-in recipients can accept in My invitations. Email delivery is available through web-issued invitations."
            : result.Records.Rows.Count == 0 ? "No pending invitations for this account." : "";
    }

    private void InvitationChanged(object sender, CurrentRowChangedEventArgs e) => UpdateActions();
    private void EmailChanged(object? sender, EventArgs e) => UpdateActions();

    private async void IssueClicked(object? sender, EventArgs e) => await UpdateInviteAsync(null, false);
    private async void ResendClicked(object? sender, EventArgs e) => await UpdateInviteAsync(Selected, false);
    private async void RevokeClicked(object? sender, EventArgs e) => await UpdateInviteAsync(Selected, true);

    private async Task UpdateInviteAsync(DataRow? selection, bool revoke)
    {
        if (!workspace.HasValue || repository is null)
            return;
        await RunAsync(async () =>
        {
            await repository.UpdateWorkspaceInvitationAsync(workspace.Value, selection?.Field<int>("id"),
                selection?.Field<string>("revision"), emailInput.Text, roleInput.SelectedItem?.Text, revoke, lifetime.Token);
            if (selection is null)
                emailInput.Text = "";
            await ReadAsync();
            statusLabel.Text = revoke ? "Invitation revoked." :
                "Invitation saved. The signed-in recipient can accept it in My invitations.";
        });
    }

    private async void AcceptClicked(object? sender, EventArgs e)
    {
        if (repository is null || Selected is not DataRow invitation)
            return;
        await RunAsync(async () => AcceptedWorkspace = await repository.AcceptWorkspaceInvitationAsync(
            invitation.Field<int>("id"), invitation.Field<string>("revision")!, lifetime.Token));
        if (AcceptedWorkspace.HasValue)
            DialogResult = DialogResult.OK;
    }

    private async Task RunAsync(Func<Task> action)
    {
        if (repository is null || busy)
            return;
        busy = true;
        UpdateActions();
        statusLabel.Text = "Working with invitations…";
        try { await action(); }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or Npgsql.NpgsqlException or TimeoutException)
        {
            if (!lifetime.IsCancellationRequested)
                statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException
                    ? error.Message : "Could not complete this invitation action. Check PostgreSQL and retry.";
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
        string? status = Selected?.Field<string>("status");
        emailInput.Enabled = roleInput.Enabled = !busy && canIssue;
        issueButton.Enabled = emailInput.Enabled && !string.IsNullOrWhiteSpace(emailInput.Text);
        resendButton.Enabled = !busy && canIssue && status is ("pending" or "expired");
        revokeButton.Enabled = !busy && canRevoke && status == "pending";
        acceptButton.Enabled = !busy && canIssue && status == "pending";
        closeButton.Enabled = !busy;
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
