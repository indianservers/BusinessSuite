using Npgsql;

namespace Business_Suite;

public sealed partial class SalesOrderActivityForm : Form
{
    private readonly SalesOrderRepository? repository;
    private readonly int order;
    private readonly bool stageHistory;
    private bool loading;

    public SalesOrderActivityForm() => InitializeComponent();
    internal SalesOrderActivityForm(SalesOrderRepository repository, int order, string number) : this()
    {
        this.repository = repository;
        this.order = order;
        orderLabel.Text = $"Activity for {number}";
    }

    internal SalesOrderActivityForm(SalesOrderRepository repository, int order, string number, bool stageHistory)
        : this(repository, order, number)
    {
        this.stageHistory = stageHistory;
        if (stageHistory)
        {
            Text = "Recorded stage history";
            orderLabel.Text = $"Recorded stage history for {number}";
        }
    }

    private async void RefreshClicked(object sender, EventArgs e)
    {
        if (loading || repository is null)
            return;
        loading = true;
        refreshButton.Enabled = false;
        activityGrid.DataSource = null;
        CopySelected();
        statusLabel.Text = stageHistory ? "Loading stage history..." : "Loading order activity...";
        try
        {
            var rows = stageHistory ? await repository.SalesOrderStageHistoryAsync(order)
                : await repository.SalesOrderActivityAsync(order);
            if (IsDisposed)
                return;
            activityGrid.DataSource = rows;
            CopySelected();
            statusLabel.Text = rows.Count switch
            {
                0 when stageHistory => "No recorded stage transitions. Earlier stage durations are unknown.",
                0 => "No scoped activity records for this order.",
                30 when stageHistory => "Showing the 30 most recent recorded transitions.",
                30 => "Showing the 30 most recent activity records.",
                _ => ""
            };
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException or InvalidOperationException)
        {
            if (!IsDisposed)
                statusLabel.Text = error is UnauthorizedAccessException or InvalidOperationException ? error.Message :
                    stageHistory ? "Could not load recorded stage history. Refresh to try again."
                        : "Could not load order activity. Check the database connection and refresh.";
        }
        finally
        {
            loading = false;
            if (!IsDisposed)
                refreshButton.Enabled = true;
        }
    }

    private void SelectionChanged(object sender, EventArgs e) => CopySelected();

    private void CopySelected()
    {
        if (beforeBox is null || afterBox is null || reasonBox is null)
            return;
        var row = activityGrid.CurrentRow?.DataBoundItem as SalesOrderActivityRow;
        beforeBox.Text = row?.Before ?? "";
        afterBox.Text = row?.After ?? "";
        reasonBox.Text = row?.Reason ?? "";
    }
}
