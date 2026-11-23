using Npgsql;

namespace Business_Suite;

public sealed partial class PosReturnHistoryForm : Form
{
    private readonly SalesOrderRepository? repository;
    private bool loading;
    private int sequence;

    public PosReturnHistoryForm() => InitializeComponent();
    internal PosReturnHistoryForm(SalesOrderRepository repository) : this() => this.repository = repository;

    private async void HistoryShown(object sender, EventArgs e) => await LoadHistoryAsync();
    private async void RefreshClicked(object sender, EventArgs e) => await LoadHistoryAsync();

    private async Task LoadHistoryAsync()
    {
        if (repository is null || loading)
            return;
        loading = true;
        refreshButton.Enabled = false;
        returnsGrid.DataSource = null;
        statusLabel.Text = "Loading return register…";
        try
        {
            var rows = await repository.ListPosReturnHistoryAsync(searchBox.Text);
            if (IsDisposed)
                return;
            returnsGrid.DataSource = rows;
            statusLabel.Text = rows.Count == 0 ? "No scoped returns match the filter."
                : rows.Count == 100 ? "Showing the latest 100 returns. Refine the search for older returns." : "";
        }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException or NpgsqlException or TimeoutException)
        {
            if (!IsDisposed)
                statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException ? error.Message
                    : "Could not load the return register. Check PostgreSQL and refresh.";
        }
        finally
        {
            loading = false;
            if (!IsDisposed)
                refreshButton.Enabled = true;
        }
    }

    private async void ReturnSelected(object sender, EventArgs e)
    {
        int selectedSequence = ++sequence;
        detailsGrid.DataSource = null;
        if (repository is null || returnsGrid.CurrentRow?.DataBoundItem is not PosReturnHistoryRow selected)
        {
            summaryLabel.Text = "Return details";
            return;
        }
        try
        {
            var detail = await repository.LoadPosReturnHistoryAsync(selected.Id);
            if (IsDisposed || sequence != selectedSequence)
                return;
            detailsGrid.DataSource = detail.Lines;
            summaryLabel.Text = $"{detail.Return.Number} · Tax {detail.Return.Currency} {detail.Return.Tax:N2}" +
                (detail.Return.Reason.Length == 0 ? "" : $" · {detail.Return.Reason}");
        }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException or NpgsqlException or TimeoutException)
        {
            if (!IsDisposed && sequence == selectedSequence)
                summaryLabel.Text = error is InvalidOperationException or UnauthorizedAccessException ? error.Message
                    : "Could not open this return.";
        }
    }
}
