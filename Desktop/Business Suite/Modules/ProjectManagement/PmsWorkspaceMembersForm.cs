using System.Data;
using Telerik.WinControls.UI;

namespace Business_Suite;

internal sealed partial class PmsWorkspaceMembersForm : Form
{
    private readonly PmsProjectRepository? repository;
    private readonly int workspace;
    private readonly PmsWorkspaceChoice? choice;
    private readonly CancellationTokenSource lifetime = new();
    private bool busy;
    private bool canAdd;
    private bool canAppointAdmin;

    public PmsWorkspaceMembersForm()
    {
        InitializeComponent();
        UpdateControls();
    }

    internal PmsWorkspaceMembersForm(PmsProjectRepository repository, PmsWorkspaceChoice choice) : this()
    {
        this.repository = repository;
        workspace = choice.Id;
        this.choice = choice;
        heading.Text = choice.Name;
        UpdateControls();
    }

    public bool MembershipChanged { get; private set; }
    private DataRow? SelectedMember => (memberGrid.CurrentRow?.DataBoundItem as DataRowView)?.Row;

    private async void MembersLoaded(object? sender, EventArgs e) => await RunAsync(async () =>
    {
        await ReadMembersAsync();
        if (canAdd)
            await ReadChoicesAsync();
    }, "Loading workspace members…");

    private async Task ReadMembersAsync()
    {
        var members = await repository!.ReadWorkspaceMembersAsync(workspace, lifetime.Token);
        if (lifetime.IsCancellationRequested)
            return;
        canAdd = members.CanAdd;
        canAppointAdmin = members.CanAppointAdmin;
        roleInput.Items[2].Enabled = canAppointAdmin;
        if (!canAppointAdmin && roleInput.SelectedIndex == 2)
            roleInput.SelectedIndex = 0;
        memberGrid.DataSource = members.Records.DefaultView;
        statusLabel.Text = members.Records.Rows.Count == 0 ? "No workspace members are visible." : "";
    }

    private async Task ReadChoicesAsync()
    {
        var choices = await repository!.ReadEligibleWorkspaceMembersAsync(workspace, searchInput.Text, lifetime.Token);
        if (lifetime.IsCancellationRequested)
            return;
        personInput.Items.Clear();
        foreach (DataRow row in choices.Rows)
            personInput.Items.Add(new RadListDataItem($"{row["name"]} · {row["email"]}") { Value = row["id"] });
        statusLabel.Text = choices.Rows.Count == 0 ? "No eligible people match the search." : "";
    }

    private async void SearchClicked(object? sender, EventArgs e) =>
        await RunAsync(ReadChoicesAsync, "Locating eligible people…");

    private async void SearchKeyDown(object? sender, KeyEventArgs e)
    {
        if (e.KeyCode != Keys.Enter)
            return;
        e.SuppressKeyPress = true;
        await RunAsync(ReadChoicesAsync, "Locating eligible people…");
    }

    private void ChoiceChanged(object? sender, EventArgs e) => UpdateControls();
    private void MemberSelectionChanged(object sender, CurrentRowChangedEventArgs e) => UpdateControls();

    private void InvitationsClicked(object? sender, EventArgs e)
    {
        if (repository is null || choice is null)
            return;
        using var invitations = new PmsWorkspaceInvitationsForm(repository, choice);
        invitations.ShowDialog(this);
    }

    private async void ChangeRoleClicked(object? sender, EventArgs e)
    {
        if (changeRoleButton.Enabled && roleInput.SelectedItem is not null)
            await ChangeMemberAsync(roleInput.SelectedItem.Text);
    }

    private async void RemoveClicked(object? sender, EventArgs e)
    {
        if (!removeButton.Enabled || SelectedMember is not DataRow member)
            return;
        if (MessageBox.Show(this, $"Remove {member["name"]} from this workspace?", "Remove workspace member",
                MessageBoxButtons.YesNo, MessageBoxIcon.Question, MessageBoxDefaultButton.Button2) == DialogResult.Yes)
            await ChangeMemberAsync(null);
    }

    private async Task ChangeMemberAsync(string? role)
    {
        if (repository is null || SelectedMember is not DataRow member)
            return;
        await RunAsync(async () =>
        {
            await repository.ChangeWorkspaceMemberAsync(workspace, member.Field<int>("id"),
                member.Field<string>("revision")!, role, lifetime.Token);
            MembershipChanged = true;
            await ReadMembersAsync();
            if (canAdd)
                await ReadChoicesAsync();
            statusLabel.Text = role is null ? "Workspace member removed." : "Workspace role updated.";
        }, "Updating workspace membership…");
    }

    private async void AddClicked(object? sender, EventArgs e)
    {
        if (repository is null || personInput.SelectedValue is not int id || roleInput.SelectedItem is null || !addButton.Enabled)
            return;
        string role = roleInput.SelectedItem.Text;
        await RunAsync(async () =>
        {
            await repository.AddWorkspaceMemberAsync(workspace, id, role, lifetime.Token);
            MembershipChanged = true;
            await ReadMembersAsync();
            await ReadChoicesAsync();
            statusLabel.Text = "Workspace member added.";
        }, "Adding a person to the workspace…");
    }

    private async Task RunAsync(Func<Task> operation, string status)
    {
        if (repository is null || busy)
            return;
        busy = true;
        UpdateControls();
        statusLabel.Text = status;
        try
        {
            await operation();
        }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or Npgsql.NpgsqlException or TimeoutException)
        {
            if (!lifetime.IsCancellationRequested)
                statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException
                    ? error.Message : "Could not complete the workspace membership action. Check PostgreSQL and retry.";
        }
        finally
        {
            busy = false;
            if (!lifetime.IsCancellationRequested)
                UpdateControls();
        }
    }

    private void UpdateControls()
    {
        bool enabled = !busy && canAdd;
        searchInput.Enabled = searchButton.Enabled = personInput.Enabled = roleInput.Enabled = enabled;
        addButton.Enabled = enabled && personInput.SelectedValue is int;
        string? role = SelectedMember?.Field<string>("role");
        changeRoleButton.Enabled = removeButton.Enabled = enabled && role is not (null or "Owner")
            && (role != "Admin" || canAppointAdmin);
        invitationsButton.Enabled = !busy && choice?.CanManage == true;
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
