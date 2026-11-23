using Npgsql;

namespace Business_Suite;

public sealed partial class SalesInvoiceDetailForm : Form
{
    private readonly SalesOrderRepository? repository;
    private readonly int orderId;
    private readonly SalesMilestoneInvoiceLink? milestone;
    private LinkedSalesInvoice? invoice;
    private decimal? outstanding;
    private readonly Func<Task<NativeInvoicePdfData>>? historyPdf;
    private readonly Func<Task<bool>>? historyCanExport;

    public SalesInvoiceDetailForm() => InitializeComponent();
    internal SalesInvoiceDetailForm(LinkedSalesInvoiceDetails detail, Func<Task<NativeInvoicePdfData>> historyPdf,
        Func<Task<bool>> historyCanExport) : this()
    {
        this.historyPdf = historyPdf;
        this.historyCanExport = historyCanExport;
        Bind(detail);
        historyButton.Enabled = false;
        feedbackLabel.Text = $"Paid {detail.Invoice.Paid:N2} | Unpaid {detail.Invoice.Balance:N2}";
    }

    internal SalesInvoiceDetailForm(LinkedSalesInvoiceDetails detail, SalesOrderRepository repository, int orderId,
        SalesMilestoneInvoiceLink milestone) : this(detail, repository, orderId)
    {
        this.milestone = milestone;
    }

    internal SalesInvoiceDetailForm(LinkedSalesInvoiceDetails detail, SalesOrderRepository repository, int orderId) : this()
    {
        this.repository = repository;
        this.orderId = orderId;
        Bind(detail);
    }

    private void Bind(LinkedSalesInvoiceDetails detail)
    {
        invoice = detail.Invoice;
        headingLabel.Text = invoice.Number;
        summaryLabel.Text = $"{invoice.Status.Replace('_', ' ')} · {invoice.Currency} {invoice.Total:N2}" +
            (invoice.IssueDate is DateTime issue ? $" · Invoice date {issue:d}" : "") +
            (invoice.DueDate is DateTime due ? $" · Due {due:d}" : "");
        itemsGrid.DataSource = detail.Lines;
    }

    private async void ViewerShown(object sender, EventArgs e)
    {
        if (invoice is null)
            return;
        try
        {
            if (historyCanExport is not null)
            {
                bool canExport = await historyCanExport();
                if (!IsDisposed)
                    pdfButton.Enabled = canExport;
                return;
            }
            if (repository is null)
                return;
            if (milestone is not null)
            {
                var milestoneApproval = repository.CanApproveSalesMilestoneInvoiceAsync(orderId, invoice.Id, milestone);
                var milestoneExport = repository.CanExportLinkedInvoiceAsync();
                var milestoneCancellation = repository.CanCancelSalesMilestoneInvoiceAsync(orderId, invoice.Id, milestone);
                var milestonePayment = repository.CanRecordSalesMilestonePaymentAsync(orderId, invoice.Id, milestone);
                await Task.WhenAll(milestoneApproval, milestoneExport, milestoneCancellation, milestonePayment);
                if (!IsDisposed)
                {
                    approveButton.Enabled = milestoneApproval.Result;
                    pdfButton.Enabled = milestoneExport.Result;
                    cancelInvoiceButton.Enabled = milestoneCancellation.Result;
                    outstanding = milestonePayment.Result;
                    paymentButton.Enabled = outstanding > 0
                        || outstanding.HasValue && repository.PaymentJournal(invoice.Id).HasPending;
                }
                return;
            }
            var approval = repository.CanApproveLinkedInvoiceAsync(orderId, invoice.Id);
            var export = repository.CanExportLinkedInvoiceAsync();
            var payment = repository.CanRecordSalesPaymentAsync(orderId, invoice.Id);
            var cancellation = repository.CanCancelLinkedInvoiceAsync(orderId, invoice.Id);
            await Task.WhenAll(approval, export, payment, cancellation);
            if (!IsDisposed)
            {
                approveButton.Enabled = approval.Result;
                pdfButton.Enabled = export.Result;
                cancelInvoiceButton.Enabled = cancellation.Result;
                outstanding = payment.Result;
                paymentButton.Enabled = outstanding > 0
                    || outstanding.HasValue && repository.PaymentJournal(invoice.Id).HasPending;
            }
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or InvalidOperationException)
        {
            if (!IsDisposed)
                feedbackLabel.Text = "Could not check invoice action access.";
        }
    }

    private async void CancelInvoiceClicked(object sender, EventArgs e)
    {
        if (repository is null || invoice is null || !cancelInvoiceButton.Enabled)
            return;
        using var editor = new SalesInvoiceCancellationForm(repository, orderId, invoice, milestone);
        if (editor.ShowDialog(this) != DialogResult.OK || IsDisposed)
            return;
        cancelInvoiceButton.Enabled = approveButton.Enabled = paymentButton.Enabled = false;
        feedbackLabel.Text = "Invoice cancelled.";
        try
        {
            var saved = milestone is null ? await repository.LoadOrderInvoiceAsync(orderId)
                : await repository.LoadSalesMilestoneInvoiceAsync(orderId, milestone.Engagement, milestone.Plan, milestone.Milestone);
            if (!IsDisposed)
                Bind(saved);
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException or InvalidOperationException)
        {
            if (!IsDisposed)
                feedbackLabel.Text = "Invoice cancelled. Reopen to refresh.";
        }
        finally
        {
            if (!IsDisposed)
                ViewerShown(this, EventArgs.Empty);
        }
    }

    private async void HistoryClicked(object sender, EventArgs e)
    {
        if (repository is null || invoice is null)
            return;
        using var history = new SalesReceiptHistoryForm(repository, orderId, invoice, milestone);
        history.ShowDialog(this);
        if (!history.Changed || IsDisposed)
            return;
        try
        {
            Bind(milestone is null ? await repository.LoadOrderInvoiceAsync(orderId)
                : await repository.LoadSalesMilestoneInvoiceAsync(orderId, milestone.Engagement, milestone.Plan, milestone.Milestone));
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException or InvalidOperationException)
        {
            if (!IsDisposed)
                feedbackLabel.Text = "Payment reversed. Reopen to refresh.";
        }
        finally
        {
            if (!IsDisposed)
                ViewerShown(this, EventArgs.Empty);
        }
    }

    private async void PaymentClicked(object sender, EventArgs e)
    {
        if (repository is null || invoice is null || outstanding is not decimal balance || !paymentButton.Enabled)
            return;
        using var editor = new SalesInvoicePaymentForm(repository, orderId, invoice, balance, milestone);
        if (editor.ShowDialog(this) != DialogResult.OK || editor.SavedPayment is not { } payment || IsDisposed)
            return;
        paymentButton.Enabled = false;
        feedbackLabel.Text = payment.Reversed ? $"Receipt {payment.Number} was reversed." : $"Receipt {payment.Number} saved.";
        try
        {
            var saved = milestone is null ? await repository.LoadOrderInvoiceAsync(orderId)
                : await repository.LoadSalesMilestoneInvoiceAsync(orderId, milestone.Engagement, milestone.Plan, milestone.Milestone);
            if (!IsDisposed)
                Bind(saved);
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException or InvalidOperationException)
        {
            if (!IsDisposed)
                feedbackLabel.Text = $"Receipt {payment.Number} saved. Reopen to refresh.";
        }
        finally
        {
            if (!IsDisposed)
                ViewerShown(this, EventArgs.Empty);
        }
    }

    private async void PdfClicked(object sender, EventArgs e)
    {
        if ((repository is null && historyPdf is null) || invoice is null || !pdfButton.Enabled)
            return;
        string filename = string.Concat(invoice.Number.Select(ch => Path.GetInvalidFileNameChars().Contains(ch) ? '_' : ch));
        pdfDialog.FileName = filename + ".pdf";
        if (pdfDialog.ShowDialog(this) != DialogResult.OK)
            return;
        pdfButton.Enabled = false;
        try
        {
            var source = historyPdf is not null ? await historyPdf()
                : milestone is null ? await repository!.LoadLinkedInvoicePdfAsync(orderId, invoice.Id)
                : await repository!.LoadSalesMilestoneInvoicePdfAsync(orderId, milestone.Engagement,
                    milestone.Plan, milestone.Milestone, invoice.Id);
            byte[] content = SalesInvoicePdf.Render(source);
            File.WriteAllBytes(pdfDialog.FileName, content);
            if (!IsDisposed)
                feedbackLabel.Text = "Invoice PDF saved.";
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException
            or InvalidOperationException or IOException or ArgumentException)
        {
            if (!IsDisposed)
                feedbackLabel.Text = error is UnauthorizedAccessException or InvalidOperationException
                    ? error.Message : "Could not save the invoice PDF. Check the destination and try again.";
        }
        finally
        {
            if (!IsDisposed)
                pdfButton.Enabled = true;
        }
    }

    private async void ApproveClicked(object sender, EventArgs e)
    {
        if (repository is null || invoice is null || !approveButton.Enabled)
            return;
        approveButton.Enabled = false;
        feedbackLabel.Text = "Approving invoice…";
        try
        {
            LinkedSalesInvoiceDetails saved;
            if (milestone is null)
            {
                await repository.ApproveLinkedInvoiceAsync(orderId, invoice.Id);
                saved = await repository.LoadOrderInvoiceAsync(orderId);
            }
            else
            {
                await repository.ApproveSalesMilestoneInvoiceAsync(orderId, invoice.Id, milestone);
                saved = await repository.LoadSalesMilestoneInvoiceAsync(orderId, milestone.Engagement, milestone.Plan, milestone.Milestone);
            }
            if (!IsDisposed)
            {
                Bind(saved);
                feedbackLabel.Text = "Invoice approved.";
                ViewerShown(this, EventArgs.Empty);
            }
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException or InvalidOperationException)
        {
            if (!IsDisposed)
            {
                feedbackLabel.Text = error is InvalidOperationException or UnauthorizedAccessException
                    ? error.Message : "Could not complete approval. Reopen the invoice to check its status.";
                ViewerShown(this, EventArgs.Empty);
            }
        }
    }
}
