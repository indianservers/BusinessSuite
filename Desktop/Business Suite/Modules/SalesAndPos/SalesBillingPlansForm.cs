using Npgsql;

namespace Business_Suite;

public sealed partial class SalesBillingPlansForm : Form
{
    private readonly SalesOrderRepository? repository;
    private readonly int order;
    private readonly int engagement;
    private bool busy;
    private int selectionVersion;

    public SalesBillingPlansForm() => InitializeComponent();
    internal SalesBillingPlansForm(SalesOrderRepository repository, int order, SalesEngagementRow engagement) : this()
    {
        this.repository = repository;
        this.order = order;
        this.engagement = engagement.Id;
        headingLabel.Text = $"Billing plans for {engagement.Number}";
    }

    private async void RefreshClicked(object sender, EventArgs e) => await LoadAsync(null);
    private async void ActivateClicked(object sender, EventArgs e) => await LoadAsync("active");
    private async void PauseClicked(object sender, EventArgs e) => await LoadAsync("paused");
    private async void CompleteClicked(object sender, EventArgs e) => await LoadAsync("completed");
    private async void CancelClicked(object sender, EventArgs e) => await LoadAsync("cancelled");
    private async void DraftDueClicked(object sender, EventArgs e) => await LoadAsync("draft_recurring");
    private void GuardClosing(object sender, FormClosingEventArgs e) => e.Cancel = busy;
    private void MilestoneSelectionChanged(object sender, EventArgs e) => UpdateButtons();
    private async void EligibilityClicked(object sender, EventArgs e) => await LoadMilestonesAsync(eligible: true);
    private async void AllMilestonesClicked(object sender, EventArgs e) => await LoadMilestonesAsync(eligible: false);
    private async void MilestoneClicked(object sender, EventArgs e)
    {
        if (repository is null || busy || planGrid.CurrentRow?.DataBoundItem is not SalesBillingPlanRow plan ||
            milestoneGrid.CurrentRow?.DataBoundItem is not SalesBillingMilestoneRow milestone)
            return;
        using var editor = new SalesBillingMilestoneForm(repository, order, engagement, plan.Id, milestone);
        if (editor.ShowDialog(this) == DialogResult.OK)
        {
            await LoadAsync(null);
            await LoadMilestonesAsync(eligible: false);
        }
    }

    private async void AddMilestoneClicked(object sender, EventArgs e)
    {
        if (repository is null || busy || planGrid.CurrentRow?.DataBoundItem is not SalesBillingPlanRow plan)
            return;
        using var editor = new SalesBillingMilestoneForm(repository, order, engagement, plan.Id);
        if (editor.ShowDialog(this) == DialogResult.OK)
        {
            await LoadAsync(null);
            await LoadMilestonesAsync(eligible: false);
        }
    }

    private async void RecurrenceClicked(object sender, EventArgs e)
    {
        if (repository is null || busy || planGrid.CurrentRow?.DataBoundItem is not SalesBillingPlanRow plan)
            return;
        using var editor = new SalesRecurringScheduleForm(repository, order, engagement, plan);
        if (editor.ShowDialog(this) == DialogResult.OK && editor.Result is { } result)
        {
            await LoadAsync(null);
            if (!IsDisposed)
                statusLabel.Text = $"Occurrences added {result.Created} · Existing dates skipped {result.Skipped}";
        }
    }

    private async Task LoadAsync(string? status)
    {
        if (repository is null || busy)
            return;
        var selected = planGrid.CurrentRow?.DataBoundItem as SalesBillingPlanRow;
        busy = true;
        UpdateButtons();
        try
        {
            List<SalesInvoiceDraftResult>? drafted = null;
            if (status == "draft_recurring" && selected is not null)
                drafted = await repository.DraftDueSalesRecurringInvoicesAsync(order, engagement, selected.Id);
            else if (status is not null && selected is not null)
                await repository.AdvanceSalesBillingPlanAsync(order, engagement, selected.Id, selected.Status, status);
            var rows = await repository.SalesBillingPlansAsync(order, engagement);
            if (IsDisposed)
                return;
            planGrid.DataSource = rows;
            if (selected is not null && planGrid.Rows.FirstOrDefault(row =>
                row.DataBoundItem is SalesBillingPlanRow data && data.Id == selected.Id) is { } matching)
                planGrid.CurrentRow = matching;
            statusLabel.Text = drafted is { Count: 0 } ? "No approved recurring milestones are due."
                : drafted is { Count: 1 } ? $"Created draft {drafted[0].Number}."
                : drafted is not null ? $"Created {drafted.Count} recurring invoice drafts."
                : rows.Count == 0 ? "No scoped billing plans for this engagement."
                : status is not null ? $"Billing plan status saved as {status}." : "";
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException or
            InvalidOperationException or ArgumentException)
        {
            if (!IsDisposed)
                statusLabel.Text = error is NpgsqlException or TimeoutException ? "Could not confirm the action. Reload the billing plan."
                    : error.Message;
        }
        finally
        {
            busy = false;
            if (!IsDisposed)
                UpdateButtons();
        }
    }

    private async void SelectionChanged(object sender, EventArgs e) => await LoadMilestonesAsync(eligible: false);

    private async Task LoadMilestonesAsync(bool eligible)
    {
        int version = ++selectionVersion;
        if (milestoneGrid is null)
            return;
        milestoneGrid.DataSource = null;
        UpdateButtons();
        if (repository is null || planGrid.CurrentRow?.DataBoundItem is not SalesBillingPlanRow selected)
            return;
        try
        {
            var rows = eligible
                ? await repository.SalesBillingEligibilityAsync(order, engagement, selected.Id, fromPicker.Value, untilPicker.Value)
                : await repository.SalesBillingMilestonesAsync(order, engagement, selected.Id);
            if (!IsDisposed && version == selectionVersion)
            {
                milestoneGrid.DataSource = rows;
                if (eligible)
                    statusLabel.Text = rows.Count == 1 ? "1 eligible milestone in this period." : $"{rows.Count} eligible milestones in this period.";
            }
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException or ArgumentException)
        {
            if (!IsDisposed && version == selectionVersion)
                statusLabel.Text = error is UnauthorizedAccessException or ArgumentException ? error.Message : "Could not load billing milestones.";
        }
    }

    private void UpdateButtons()
    {
        if (refreshButton is null || activateButton is null)
            return;
        string status = (planGrid.CurrentRow?.DataBoundItem as SalesBillingPlanRow)?.Status ?? "";
        planGrid.Enabled = refreshButton.Enabled = !busy;
        activateButton.Text = status == "paused" ? "Resume plan" : "Activate plan";
        activateButton.Enabled = !busy && SalesOrderRepository.IsBillingPlanTransition(status, "active");
        pauseButton.Enabled = !busy && SalesOrderRepository.IsBillingPlanTransition(status, "paused");
        completeButton.Enabled = !busy && SalesOrderRepository.IsBillingPlanTransition(status, "completed");
        cancelButton.Enabled = !busy && SalesOrderRepository.IsBillingPlanTransition(status, "cancelled");
        eligibilityButton.Enabled = allMilestonesButton.Enabled = !busy && status.Length > 0;
        milestoneButton.Enabled = !busy && milestoneGrid.CurrentRow?.DataBoundItem is SalesBillingMilestoneRow;
        addMilestoneButton.Enabled = !busy && status.Length > 0;
        recurrenceButton.Enabled = !busy && status is not ("" or "completed" or "cancelled");
        draftDueButton.Enabled = !busy && status == "active";
    }
}
