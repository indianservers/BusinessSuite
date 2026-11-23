using Npgsql;

namespace Business_Suite;

public sealed partial class SalesInvoiceCancellationForm : Form
{
    private readonly SalesOrderRepository? repository;
    private readonly int orderId;
    private readonly int invoiceId;
    private readonly SalesMilestoneInvoiceLink? milestone;
    private bool cancelling;

    public SalesInvoiceCancellationForm() => InitializeComponent();

    internal SalesInvoiceCancellationForm(SalesOrderRepository repository, int order, LinkedSalesInvoice invoice,
        SalesMilestoneInvoiceLink? milestone = null) : this()
    {
        this.repository = repository;
        orderId = order;
        invoiceId = invoice.Id;
        this.milestone = milestone;
        headingLabel.Text = $"Cancel invoice {invoice.Number}";
    }

    private void ReasonChanged(object sender, EventArgs e) =>
        cancelInvoiceButton.Enabled = repository is not null && !cancelling && reasonBox.Text.Trim().Length >= 3;

    private async void CancelInvoiceClicked(object sender, EventArgs e)
    {
        if (repository is null || cancelling || !cancelInvoiceButton.Enabled)
            return;
        cancelling = true;
        cancelInvoiceButton.Enabled = reasonBox.Enabled = closeButton.Enabled = false;
        statusLabel.Text = "Cancelling invoice…";
        try
        {
            if (milestone is null)
                await repository.CancelLinkedInvoiceAsync(orderId, invoiceId, reasonBox.Text);
            else
                await repository.CancelSalesMilestoneInvoiceAsync(orderId, invoiceId, reasonBox.Text, milestone);
            DialogResult = DialogResult.OK;
        }
        catch (Exception error) when (error is InvalidOperationException or NpgsqlException or UnauthorizedAccessException
            or TimeoutException or ArgumentException)
        {
            if (!IsDisposed)
                statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException or ArgumentException ? error.Message
                    : "Could not confirm cancellation. Reopen the invoice to check its status.";
        }
        finally
        {
            cancelling = false;
            if (!IsDisposed)
            {
                reasonBox.Enabled = closeButton.Enabled = true;
                ReasonChanged(this, EventArgs.Empty);
            }
        }
    }

    private void CancellationClosing(object sender, FormClosingEventArgs e)
    {
        if (cancelling && DialogResult != DialogResult.OK)
            e.Cancel = true;
    }
}
