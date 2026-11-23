using System.Data;
using Telerik.WinControls.UI;

namespace Business_Suite;

internal sealed partial class PmsMilestonesForm : Form
{
    private readonly PmsProjectRepository? repository;
    private readonly int project;
    private readonly CancellationTokenSource lifetime = new();
    private PmsMilestoneList? milestones;
    private DataRow? draftRow;
    private bool editing;
    private bool busy;
    private bool bindingEditor;

    public PmsMilestonesForm() => InitializeComponent();

    internal PmsMilestonesForm(PmsProjectRepository repository, DataRow selected) : this()
    {
        this.repository = repository;
        project = selected.Field<int>("id");
        heading.Text = selected.Field<string>("name");
        UpdateActions();
    }

    private DataRow? Selected => (grid.CurrentRow?.DataBoundItem as DataRowView)?.Row;
    private bool CanEditSelected => Selected is DataRow row
        && row.Field<string>("client_approval_status") is not ("Pending" or "Approved");

    private async void MilestonesLoaded(object? sender, EventArgs e) => await RunAsync(ReadAsync);

    private async Task ReadAsync()
    {
        milestones = await repository!.ListMilestonesAsync(project, lifetime.Token);
        if (lifetime.IsCancellationRequested)
            return;
        grid.DataSource = milestones.Rows.DefaultView;
        statusText.Text = milestones.Rows.Rows.Count == 0 ? "No milestones for this project." : "";
    }

    private void SelectionChanged(object sender, CurrentRowChangedEventArgs e) => UpdateActions();
    private void NewClicked(object? sender, EventArgs e) => OpenEditor(null);

    private void EditClicked(object? sender, EventArgs e)
    {
        if (CanEditSelected)
            OpenEditor(Selected);
    }

    private void OpenEditor(DataRow? row)
    {
        editing = true;
        draftRow = row;
        bindingEditor = true;
        nameInput.Text = row?.Field<string>("name") ?? "";
        descriptionInput.Text = row?.Field<string>("description") ?? "";
        statusInput.SelectedItem = statusInput.Items.FirstOrDefault(i => i.Text == (row?.Field<string>("status") ?? "Not Started"));
        SetDate(startInput, row?.Field<DateTime?>("start_date"));
        SetDate(dueInput, row?.Field<DateTime?>("due_date"));
        progressInput.Value = row?.Field<int>("progress") ?? 0;
        ownerInput.Items.Clear();
        ownerInput.Items.Add(new RadListDataItem("Unassigned"));
        if (milestones is not null)
            foreach (DataRow person in milestones.Owners.Rows)
                ownerInput.Items.Add(new RadListDataItem(person.Field<string>("name")!) { Value = person.Field<int>("id") });
        int? owner = row?.Field<int?>("owner_user_id");
        if (owner.HasValue && !ownerInput.Items.Any(item => Equals(item.Value, owner.Value)))
            ownerInput.Items.Add(new RadListDataItem("Retain existing owner") { Value = owner.Value });
        ownerInput.SelectedIndex = 0;
        if (owner.HasValue)
            ownerInput.SelectedValue = owner.Value;
        bindingEditor = false;
        statusText.Text = "";
        UpdateActions();
        nameInput.Focus();
    }

    private static void SetDate(RadDateTimePicker input, DateTime? value)
    {
        if (value.HasValue)
            input.Value = value.Value;
        input.Checked = value.HasValue;
    }

    private void MilestoneStatusChanged(object? sender, EventArgs e)
    {
        if (bindingEditor)
            return;
        if (statusInput.SelectedItem?.Text == "Completed")
            progressInput.Value = 100;
        else if (progressInput.Value == 100)
            progressInput.Value = 0;
    }

    private async void SaveClicked(object? sender, EventArgs e)
    {
        if (!editing || repository is null)
            return;
        string? description = descriptionInput.Text.Length == 0 ? null : descriptionInput.Text;
        var draft = new PmsMilestoneDraft(nameInput.Text, description, statusInput.SelectedItem?.Text ?? "",
            startInput.Checked ? startInput.Value.Date : null, dueInput.Checked ? dueInput.Value.Date : null,
            (int)progressInput.Value, ownerInput.SelectedValue is int owner ? owner : null);
        await RunAsync(async () =>
        {
            await repository.SaveMilestoneAsync(project, draftRow?.Field<int>("id"), draftRow?.Field<string>("revision"),
                draft, lifetime.Token);
            editing = false;
            draftRow = null;
            await ReadAsync();
            statusText.Text = "Milestone saved.";
        });
    }

    private async void SubmitClicked(object? sender, EventArgs e)
    {
        if (repository is null || !submitButton.Enabled || Selected is not DataRow row)
            return;
        await RunAsync(async () =>
        {
            await repository.SubmitMilestoneApprovalAsync(project, row.Field<int>("id"),
                row.Field<string>("revision")!, lifetime.Token);
            await ReadAsync();
            statusText.Text = "Milestone submitted for client approval.";
        });
    }

    private void ReasonChanged(object? sender, EventArgs e) => UpdateActions();

    private async void ApproveClicked(object? sender, EventArgs e) => await DecideAsync(true);
    private async void RejectClicked(object? sender, EventArgs e) => await DecideAsync(false);

    private async Task DecideAsync(bool approve)
    {
        if (repository is null || !(approve ? approveButton.Enabled : rejectButton.Enabled)
            || Selected is not DataRow row)
            return;
        await RunAsync(async () =>
        {
            await repository.DecideMilestoneApprovalAsync(project, row.Field<int>("id"),
                row.Field<string>("revision")!, approve, reasonInput.Text, lifetime.Token);
            reasonInput.Clear();
            await ReadAsync();
            statusText.Text = approve ? "Milestone approved." : "Milestone rejected.";
        });
    }

    private void CancelEditClicked(object? sender, EventArgs e)
    {
        editing = false;
        draftRow = null;
        statusText.Text = "";
        UpdateActions();
    }

    private void CloseClicked(object? sender, EventArgs e) => Close();

    private async Task RunAsync(Func<Task> action)
    {
        if (repository is null || busy)
            return;
        busy = true;
        UpdateActions();
        statusText.Text = "Working with milestones…";
        try { await action(); }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or Npgsql.NpgsqlException or TimeoutException)
        {
            statusText.Text = error is InvalidOperationException or UnauthorizedAccessException
                ? error.Message : "Could not complete the milestone action. Check PostgreSQL and retry.";
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
        bool ready = !busy && !editing && milestones is not null;
        newButton.Enabled = ready && milestones!.CanCreate;
        editButton.Enabled = ready && milestones!.CanEdit && CanEditSelected;
        submitButton.Enabled = ready && milestones!.CanCreate && CanEditSelected;
        var canDecide = ready && milestones!.CanDecide
            && Selected?.Field<string>("client_approval_status") == "Pending";
        reasonInput.Enabled = approveButton.Enabled = canDecide;
        rejectButton.Enabled = canDecide && !string.IsNullOrWhiteSpace(reasonInput.Text);
        grid.Enabled = !editing && !busy;
        editor.Enabled = editing && !busy;
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
