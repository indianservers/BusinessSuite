using Npgsql;

namespace Business_Suite;

public sealed partial class SalesEngagementsForm : Form
{
    private readonly SalesOrderRepository? repository;
    private readonly int order;
    private bool busy;
    private int historySequence;

    public SalesEngagementsForm() => InitializeComponent();
    internal SalesEngagementsForm(SalesOrderRepository repository, int order, string number) : this()
    {
        this.repository = repository;
        this.order = order;
        headingLabel.Text = $"Engagements for {number}";
    }

    private async void RefreshClicked(object sender, EventArgs e) => await RunAsync(null);
    private async void CloseClicked(object sender, EventArgs e) => await RunAsync("close");
    private async void ReopenClicked(object sender, EventArgs e) => await RunAsync("reopen");
    private async void CancelClicked(object sender, EventArgs e) => await RunAsync("cancel");
    private async void ProjectClicked(object sender, EventArgs e) => await RunAsync("project");
    private void BillingClicked(object sender, EventArgs e)
    {
        if (repository is null || busy || engagementsGrid.CurrentRow?.DataBoundItem is not SalesEngagementRow selected)
            return;
        using var plans = new SalesBillingPlansForm(repository, order, selected);
        plans.ShowDialog(this);
    }
    private void ReasonChanged(object sender, EventArgs e) => UpdateActions();
    private void GuardClosing(object sender, FormClosingEventArgs e) => e.Cancel = busy;

    private async Task RunAsync(string? action)
    {
        if (repository is null || busy)
            return;
        var selected = engagementsGrid.CurrentRow?.DataBoundItem as SalesEngagementRow;
        busy = true;
        UpdateActions();
        try
        {
            SalesEngagementProject? project = null;
            if (action == "project" && selected is not null)
                project = await repository.CreateEngagementProjectAsync(order, selected.Id);
            else if (action is not null && selected is not null)
                await repository.ChangeSalesEngagementAsync(order, selected.Id, selected.Status, action, reasonBox.Text);
            var rows = await repository.SalesEngagementsAsync(order);
            if (IsDisposed)
                return;
            engagementsGrid.DataSource = rows;
            if (selected is not null && engagementsGrid.Rows.FirstOrDefault(row =>
                row.DataBoundItem is SalesEngagementRow data && data.Id == selected.Id) is { } matching)
                engagementsGrid.CurrentRow = matching;
            reasonBox.Clear();
            statusLabel.Text = rows.Count == 0 ? "No scoped engagements for this order." : action switch
            {
                "close" => "Engagement closed.",
                "cancel" => "Engagement cancelled.",
                "reopen" => "Engagement reopened.",
                "project" => project is null ? "Project Management is disabled for this company." :
                    $"Delivery project {project.Key} is available in Project Management.",
                _ => ""
            };
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException or
            InvalidOperationException or ArgumentException)
        {
            if (!IsDisposed)
                statusLabel.Text = error is NpgsqlException or TimeoutException ? "Could not confirm the action. Reload the engagement."
                    : error.Message;
        }
        finally
        {
            busy = false;
            if (!IsDisposed)
                UpdateActions();
        }
    }

    private async void SelectionChanged(object sender, EventArgs e)
    {
        int sequence = ++historySequence;
        if (historyGrid is null || reasonBox is null)
            return;
        historyGrid.DataSource = null;
        reasonBox.Clear();
        UpdateActions();
        if (repository is null || engagementsGrid.CurrentRow?.DataBoundItem is not SalesEngagementRow selected)
            return;
        try
        {
            var history = await repository.SalesEngagementActionsAsync(order, selected.Id);
            if (!IsDisposed && sequence == historySequence)
                historyGrid.DataSource = history;
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException)
        {
            if (!IsDisposed && sequence == historySequence)
                statusLabel.Text = error is UnauthorizedAccessException ? error.Message : "Could not load engagement history.";
        }
    }

    private void UpdateActions()
    {
        if (refreshButton is null || reasonBox is null)
            return;
        var selected = engagementsGrid.CurrentRow?.DataBoundItem as SalesEngagementRow;
        engagementsGrid.Enabled = refreshButton.Enabled = !busy;
        reasonBox.Enabled = !busy && selected is { Status: not "cancelled" };
        projectButton.Enabled = !busy && selected is { Status: not ("closed" or "cancelled") };
        billingButton.Enabled = !busy && selected is not null;
        bool allowed = reasonBox.Enabled && !string.IsNullOrWhiteSpace(reasonBox.Text);
        reopenButton.Enabled = allowed && selected?.Status == "closed";
        closeButton.Enabled = cancelButton.Enabled = allowed && selected?.Status != "closed";
    }
}
