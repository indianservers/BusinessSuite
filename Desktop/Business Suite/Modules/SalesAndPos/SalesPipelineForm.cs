using Npgsql;

namespace Business_Suite;

public sealed partial class SalesPipelineForm : Form
{
    private readonly SalesOrderRepository? repository;
    private bool loading;
    private bool filtersLoaded;

    public SalesPipelineForm() => InitializeComponent();

    internal SalesPipelineForm(SalesOrderRepository repository) : this()
    {
        this.repository = repository;
        periodBox.DataSource = new List<string> { "This month", "Today", "This week", "All time", "Custom" };
        periodBox.SelectedIndex = 0;
    }

    private static string PeriodKey(int index) => index switch
    {
        1 => "today", 2 => "week", 3 => "all", 4 => "custom", _ => "month"
    };

    private void PeriodChanged(object sender, EventArgs e)
    {
        if (fromBox is not null && untilBox is not null)
            fromBox.Enabled = untilBox.Enabled = !loading && WorkWithDates;
    }

    private bool WorkWithDates => periodBox.SelectedIndex == 4;

    private async void RefreshClicked(object sender, EventArgs e) => await LoadPipelineAsync(false);
    private async void StageChanged(object sender, EventArgs e)
    {
        if (!loading)
            await LoadPipelineAsync(true);
    }

    private async Task LoadPipelineAsync(bool drillDown)
    {
        if (loading || repository is null)
            return;
        loading = true;
        UpdateButtons();
        try
        {
            string? stage = drillDown ? (stageBox.SelectedItem?.DataBoundItem as StageChoice)?.Status : null;
            if (stage == "")
                stage = null;
            if (!filtersLoaded)
            {
                var filters = await repository.SalesPipelineFiltersAsync();
                SetChoices(ownerBox, filters.Owners, "All owners");
                SetChoices(teamBox, filters.Teams, "All teams");
                SetChoices(customerBox, filters.Customers, "All customers");
                filtersLoaded = true;
            }
            var page = await repository.FilteredSalesPipelineAsync(PeriodKey(periodBox.SelectedIndex), fromBox.Value.Date,
                untilBox.Value.Date, stage, SelectedId(ownerBox), SelectedId(teamBox), SelectedId(customerBox));
            if (IsDisposed)
                return;
            var stages = new List<SalesPipelineStage> { new("", page.Stages.Sum(row => row.Count)) };
            stages.AddRange(page.Stages);
            stageBox.DisplayMember = nameof(StageChoice.Label);
            stageBox.DataSource = stages.Select(row => new StageChoice(row.Status,
                row.Status.Length == 0 ? $"All stages ({row.Count:N0})" : row.Display)).ToList();
            stageBox.SelectedIndex = Math.Max(0, stages.FindIndex(item => item.Status == (stage ?? "")));
            ordersGrid.DataSource = page.Orders;
            string range = page.From is DateTime start ? $"{start:d} to {page.Until:d}" : $"Through {page.Until:d}";
            long total = stage is null ? stages[0].Count : stages.FirstOrDefault(item => item.Status == stage)?.Count ?? 0;
            statusLabel.Text = total == 0 ? $"No authorized sales orders | {range}"
                : $"{page.Orders.Count:N0} of {total:N0} orders | {range}";
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or
            UnauthorizedAccessException or InvalidOperationException or ArgumentException)
        {
            ordersGrid.DataSource = null;
            statusLabel.Text = error is NpgsqlException or TimeoutException ? "The Sales pipeline could not load." : error.Message;
        }
        finally
        {
            loading = false;
            if (!IsDisposed)
                UpdateButtons();
        }
    }

    private async void OpenOrder(object sender, EventArgs e)
    {
        if (repository is null || loading || ordersGrid.CurrentRow?.DataBoundItem is not SalesPipelineOrder selected)
            return;
        using var overview = new SalesOrderOverviewForm(repository, selected.Id);
        overview.ShowDialog(this);
        if (overview.Changed)
            await LoadPipelineAsync(true);
    }

    private void OpenBoard(object sender, EventArgs e)
    {
        if (repository is null || loading)
            return;
        using var board = new SalesOperationalBoardForm(repository);
        board.ShowDialog(this);
    }

    private void ConfigurePipeline(object sender, EventArgs e)
    {
        if (repository is null || loading)
            return;
        using var configuration = new SalesPipelineConfigurationForm(repository);
        configuration.ShowDialog(this);
    }

    private async void OpenOperationalStage(object sender, EventArgs e)
    {
        if (repository is null || loading || ordersGrid.CurrentRow?.DataBoundItem is not SalesPipelineOrder selected)
            return;
        using var editor = new SalesOperationalPositionForm(repository, selected.Id, selected.Number);
        editor.ShowDialog(this);
        if (editor.Changed)
            await LoadPipelineAsync(true);
    }

    private void OpenStageHistory(object sender, EventArgs e)
    {
        if (repository is null || loading || ordersGrid.CurrentRow?.DataBoundItem is not SalesPipelineOrder selected)
            return;
        using var history = new SalesOrderActivityForm(repository, selected.Id, selected.Number, stageHistory: true);
        history.ShowDialog(this);
    }

    private void SelectionChanged(object sender, EventArgs e) => UpdateButtons();

    private static void SetChoices(Telerik.WinControls.UI.RadDropDownList list, List<SalesPipelineFilterChoice> options, string all)
    {
        list.DisplayMember = nameof(SalesPipelineFilterChoice.Label);
        list.DataSource = new[] { new SalesPipelineFilterChoice(0, all) }.Concat(options).ToList();
        list.SelectedIndex = 0;
    }

    private static int? SelectedId(Telerik.WinControls.UI.RadDropDownList list) =>
        list.SelectedItem?.DataBoundItem is SalesPipelineFilterChoice { Id: > 0 } choice ? choice.Id : null;

    private void UpdateButtons()
    {
        if (refreshButton is null || ordersGrid is null)
            return;
        refreshButton.Enabled = periodBox.Enabled = stageBox.Enabled = configurationButton.Enabled = operationalBoardButton.Enabled = !loading;
        ownerBox.Enabled = teamBox.Enabled = customerBox.Enabled = !loading;
        fromBox.Enabled = untilBox.Enabled = !loading && WorkWithDates;
        var selected = ordersGrid.CurrentRow?.DataBoundItem as SalesPipelineOrder;
        openButton.Enabled = stageHistoryButton.Enabled = operationalStageButton.Enabled = !loading && selected is not null;
        signalsBox.Text = selected?.Signals.Replace(" | ", Environment.NewLine) ?? "";
    }

    private void GuardClosing(object sender, FormClosingEventArgs e) => e.Cancel = loading;

    private sealed record StageChoice(string Status, string Label);
}

