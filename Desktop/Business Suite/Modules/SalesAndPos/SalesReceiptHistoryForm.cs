using Npgsql;

namespace Business_Suite;

public sealed partial class SalesReceiptHistoryForm : Form
{
    private readonly SalesOrderRepository? repository;
    private readonly int orderId;
    private readonly int invoiceId;
    private readonly SalesMilestoneInvoiceLink? milestone;
    private bool loading;
    private bool reversing;

    public SalesReceiptHistoryForm() => InitializeComponent();

    internal SalesReceiptHistoryForm(SalesOrderRepository repository, int order, LinkedSalesInvoice invoice,
        SalesMilestoneInvoiceLink? milestone = null) : this()
    {
        this.repository = repository;
        orderId = order;
        invoiceId = invoice.Id;
        this.milestone = milestone;
        Text = $"Payment history · {invoice.Number}";
    }

    internal bool Changed { get; private set; }

    private async void HistoryShown(object sender, EventArgs e) => await LoadHistoryAsync();
    private async void RefreshClicked(object sender, EventArgs e) => await LoadHistoryAsync();
    private void HistorySelectionChanged(object sender, EventArgs e)
    {
        reasonBox.Clear();
        ApplySelection();
    }
    private void ReasonChanged(object sender, EventArgs e) => ApplySelection();

    private void ApplySelection()
    {
        bool selected = !loading && !reversing && historyGrid.CurrentRow?.DataBoundItem is SalesReceiptHistoryRow { CanReverse: true };
        reasonBox.Enabled = selected;
        reverseButton.Enabled = selected && reasonBox.Text.Trim().Length >= 3;
        refreshButton.Enabled = !loading && !reversing;
        closeButton.Enabled = !reversing;
    }

    private async Task LoadHistoryAsync(string? success = null)
    {
        if (repository is null || loading || reversing)
            return;
        loading = true;
        ApplySelection();
        statusLabel.Text = "Loading invoice payments…";
        try
        {
            var history = milestone is null ? await repository.LoadSalesReceiptHistoryAsync(orderId, invoiceId)
                : await repository.LoadSalesMilestoneReceiptHistoryAsync(orderId, invoiceId, milestone);
            if (IsDisposed)
                return;
            summaryLabel.Text = $"Paid {history.Currency} {history.Paid:N2} · Outstanding {history.Currency} {history.Outstanding:N2}";
            historyGrid.DataSource = history.Rows;
            statusLabel.Text = success ?? (history.Rows.Count == 0 ? "No payment allocations are visible in this branch."
                : history.Rows.Count == 100 ? "Showing the latest 100 scoped payment allocations." : "");
        }
        catch (Exception error) when (error is InvalidOperationException or NpgsqlException or UnauthorizedAccessException or TimeoutException)
        {
            if (!IsDisposed)
            {
                historyGrid.DataSource = null;
                statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException ? error.Message
                    : "Could not load payment history. Check the connection and refresh.";
            }
        }
        finally
        {
            loading = false;
            if (!IsDisposed)
                ApplySelection();
        }
    }

    private async void ReverseClicked(object sender, EventArgs e)
    {
        if (repository is null || reversing || !reverseButton.Enabled ||
            historyGrid.CurrentRow?.DataBoundItem is not SalesReceiptHistoryRow { CanReverse: true } selected)
            return;
        reversing = true;
        ApplySelection();
        statusLabel.Text = $"Reversing receipt {selected.Number}…";
        string? completed = null;
        try
        {
            var saved = milestone is null ? await repository.ReverseSalesReceiptAsync(orderId, invoiceId, selected.ReceiptId, reasonBox.Text)
                : await repository.ReverseSalesMilestoneReceiptAsync(orderId, invoiceId, selected.ReceiptId, reasonBox.Text, milestone);
            Changed = true;
            completed = $"Receipt {saved.Number} reversed.";
        }
        catch (Exception error) when (error is InvalidOperationException or NpgsqlException or UnauthorizedAccessException or TimeoutException or ArgumentException)
        {
            if (!IsDisposed)
                statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException or ArgumentException ? error.Message
                    : "Could not confirm reversal. Refresh to check the receipt before retrying.";
        }
        finally
        {
            reversing = false;
            if (!IsDisposed)
                ApplySelection();
        }
        if (!IsDisposed && completed is not null)
            await LoadHistoryAsync(completed);
    }

    private void HistoryClosing(object sender, FormClosingEventArgs e) => e.Cancel = reversing;
}
