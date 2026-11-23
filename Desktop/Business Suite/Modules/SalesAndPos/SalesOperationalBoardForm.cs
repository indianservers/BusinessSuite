using System.Text.Json;
using Npgsql;

namespace Business_Suite;

public sealed partial class SalesOperationalBoardForm : Form
{
    private readonly SalesOrderRepository? repository;
    private bool busy;
    private bool canCreate;
    private int? selectedPipeline;

    public SalesOperationalBoardForm() => InitializeComponent();
    internal SalesOperationalBoardForm(SalesOrderRepository repository) : this() => this.repository = repository;

    private async void ReloadClicked(object sender, EventArgs e) => await LoadBoardAsync(null);
    private async void PipelineChanged(object sender, EventArgs e) => await LoadBoardAsync(null);
    private async void LaneChanged(object sender, EventArgs e)
    {
        if (!busy)
            await LoadBoardAsync(ActiveLane);
    }

    private string? ActiveLane => lanesGrid.CurrentRow?.DataBoundItem is SalesOperationalLane { Id.Length: > 0 } lane
        ? lane.Id : null;

    private async Task LoadBoardAsync(string? stage)
    {
        if (busy || repository is null)
            return;
        int? pipeline = pipelineBox.SelectedItem?.DataBoundItem is PipelineChoice choice ? choice.Id : selectedPipeline;
        busy = true;
        UpdateButtons();
        try
        {
            var board = await repository.SalesOperationalBoardAsync(pipeline, searchBox.Text, stage);
            canCreate = board.Selected is null && await repository.CanCreateSalesOrderAsync();
            var choices = new[] { new PipelineChoice(null, "Document workflow") }
                .Concat(board.Definitions.Select(item => new PipelineChoice(item.Id, item.Name))).ToList();
            pipelineBox.DisplayMember = nameof(PipelineChoice.Label);
            pipelineBox.DataSource = choices;
            selectedPipeline = board.Selected;
            pipelineBox.SelectedIndex = choices.FindIndex(item => item.Id == selectedPipeline);
            var lanes = new[] { new SalesOperationalLane("", "All stages", board.Lanes.Sum(item => item.Count), null, 14) }
                .Concat(board.Lanes).ToList();
            lanesGrid.DataSource = lanes;
            var active = lanesGrid.Rows.FirstOrDefault(row => (row.DataBoundItem as SalesOperationalLane)?.Id == (stage ?? ""));
            if (active is not null)
                lanesGrid.CurrentRow = active;
            ordersGrid.DataSource = board.Rows;
            long count = (active?.DataBoundItem as SalesOperationalLane)?.Count ?? 0;
            statusLabel.Text = count == 0 ? "No authorized orders match the selected stage and search."
                : $"{board.Rows.Count:N0} of {count:N0} orders";
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException or
            InvalidOperationException or ArgumentException or JsonException)
        {
            ordersGrid.DataSource = null;
            canCreate = false;
            statusLabel.Text = error is NpgsqlException or TimeoutException ? "The operational board could not load." : error.Message;
        }
        finally
        {
            busy = false;
            UpdateButtons();
        }
    }

    private async void CreateClicked(object sender, EventArgs e)
    {
        if (repository is null || busy || !canCreate)
            return;
        using var editor = new SalesOrderCreateForm(repository);
        if (editor.ShowDialog(this) == DialogResult.OK && editor.SavedOrder is { } saved)
        {
            searchBox.Text = saved.Number;
            await LoadBoardAsync("draft");
        }
    }

    private async void OrderClicked(object sender, EventArgs e)
    {
        if (repository is null || SelectedOrder is not { } row || busy)
            return;
        using var dialog = new SalesOrderOverviewForm(repository, row.Id);
        dialog.ShowDialog(this);
        if (dialog.Changed)
            await LoadBoardAsync(ActiveLane);
    }

    private async void MoveClicked(object sender, EventArgs e)
    {
        if (repository is null || SelectedOrder is not { } row || busy)
            return;
        if (selectedPipeline is null)
        {
            await AdvanceDocumentAsync(repository, row);
            return;
        }
        using var dialog = new SalesOperationalPositionForm(repository, row.Id, row.Number);
        dialog.ShowDialog(this);
        if (dialog.Changed)
            await LoadBoardAsync(ActiveLane);
    }

    private async Task AdvanceDocumentAsync(SalesOrderRepository repo, SalesOperationalBoardRow row)
    {
        if (!row.Commercial || row.DocumentStatus is not ("draft" or "approved"))
            return;
        busy = true;
        UpdateButtons();
        string? saved = null;
        try
        {
            if (!await repo.CanAdvanceApprovalAsync(row.Id, row.DocumentStatus))
                throw new InvalidOperationException("This order changed or the document action is unavailable. Refresh the board.");
            if (row.DocumentStatus == "approved")
            {
                var confirmed = await repo.ConfirmSalesOrderAsync(row.Id);
                saved = $"Confirmed {row.Number} | Billing plan #{confirmed.BillingPlanId}.";
            }
            else
            {
                var submitted = await repo.AdvanceSalesApprovalAsync(row.Id, approve: false);
                saved = submitted.ApprovalRequestId is int request
                    ? $"Submitted {row.Number} | Approval request #{request}."
                    : $"{row.Number} approved under the company approval threshold.";
            }
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException or InvalidOperationException)
        {
            statusLabel.Text = error is NpgsqlException or TimeoutException ? "The document action could not be confirmed. Refresh the board."
                : error.Message;
        }
        finally
        {
            busy = false;
            UpdateButtons();
        }
        if (saved is not null)
        {
            await LoadBoardAsync(ActiveLane);
            statusLabel.Text = saved;
        }
    }

    private void HistoryClicked(object sender, EventArgs e)
    {
        if (repository is null || SelectedOrder is not { } row || busy)
            return;
        using var history = new SalesOrderActivityForm(repository, row.Id, row.Number, stageHistory: true);
        history.ShowDialog(this);
    }

    private SalesOperationalBoardRow? SelectedOrder => ordersGrid.CurrentRow?.DataBoundItem as SalesOperationalBoardRow;
    private void SelectionChanged(object sender, EventArgs e) => UpdateButtons();
    private void GuardClosing(object sender, FormClosingEventArgs e) => e.Cancel = busy;

    private void UpdateButtons()
    {
        if (searchButton is null || ordersGrid is null)
            return;
        searchBox.Enabled = searchButton.Enabled = pipelineBox.Enabled = lanesGrid.Enabled = ordersGrid.Enabled = !busy;
        var selected = SelectedOrder;
        orderButton.Enabled = historyButton.Enabled = !busy && selected is not null;
        bool document = selectedPipeline is null;
        createButton.Enabled = !busy && document && canCreate;
        moveButton.Text = !document ? "Operational stage" : selected?.DocumentStatus == "approved" ? "Confirm order" : "Submit for approval";
        moveButton.Enabled = !busy && selected is not null && (!document ||
            selected is { Commercial: true, DocumentStatus: "draft" or "approved" });
    }

    private sealed record PipelineChoice(int? Id, string Label);
}
