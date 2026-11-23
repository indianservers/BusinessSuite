using Npgsql;

namespace Business_Suite;

public sealed partial class SalesOrderOverviewForm : Form
{
    private readonly SalesOrderRepository? repository;
    private readonly int order;
    private SalesOrderOverview? overview;
    private SalesOrderArchivePreview? archivePreview;
    private SalesOrderRevisionPreview? revisionPreview;
    private readonly Guid archiveRequest = Guid.NewGuid();
    private readonly Guid revisionRequest = Guid.NewGuid();
    private bool busy;
    private SalesSourceQuotation? sourceQuotation;
    private LinkedSalesInvoice? linkedInvoice;

    public SalesOrderOverviewForm() => InitializeComponent();
    internal SalesOrderOverviewForm(SalesOrderRepository repository, int order) : this()
    {
        this.repository = repository;
        this.order = order;
    }

    internal bool Changed { get; private set; }
    internal bool Archived { get; private set; }
    internal SalesOrderCreated? RevisedOrder { get; private set; }

    private async void SourceQuotationClicked(object sender, EventArgs e)
    {
        if (busy || repository is null)
            return;
        busy = true;
        UpdateButtons();
        try
        {
            sourceQuotation = await repository.FindSourceQuotationAsync(order);
            if (sourceQuotation is not { } source)
            {
                statusLabel.Text = "The source quotation is unavailable in this branch.";
                return;
            }
            using var dialog = new CrmQuoteLifecycleForm(source.Repository, source.Id);
            dialog.ShowDialog(this);
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException)
        {
            statusLabel.Text = "The source quotation could not be loaded.";
        }
        finally
        {
            busy = false;
            UpdateButtons();
        }
    }

    private async void LinkedInvoiceClicked(object sender, EventArgs e)
    {
        if (busy || repository is null || linkedInvoice is null)
            return;
        busy = true;
        UpdateButtons();
        try
        {
            var detail = await repository.LoadOrderInvoiceAsync(order);
            using var dialog = new SalesInvoiceDetailForm(detail, repository, order);
            dialog.ShowDialog(this);
            await LoadLinkedInvoiceAsync();
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or
            UnauthorizedAccessException or InvalidOperationException)
        {
            linkedInvoice = null;
            invoiceStatusLabel.Text = "";
            statusLabel.Text = "The linked invoice could not be loaded. Refresh the Sales order.";
        }
        finally
        {
            busy = false;
            UpdateButtons();
        }
    }

    private async Task LoadLinkedInvoiceAsync()
    {
        linkedInvoice = repository is null ? null : await repository.FindOrderInvoiceAsync(order);
        invoiceStatusLabel.Text = linkedInvoice is { } invoice
            ? $"Invoice {invoice.Status.Replace('_', ' ')} | {invoice.PaymentStatus}" : "";
    }

    private void PurchaseHistoryClicked(object sender, EventArgs e)
    {
        if (busy || repository is null || overview is null)
            return;
        using var dialog = new SalesCustomerHistoryForm(repository, order);
        dialog.ShowDialog(this);
    }

    private async void PdfClicked(object sender, EventArgs e)
    {
        if (busy || repository is null || overview is null)
            return;
        pdfDialog.FileName = string.Join("_", overview.Number.Split(Path.GetInvalidFileNameChars())) + ".pdf";
        if (pdfDialog.ShowDialog(this) != DialogResult.OK)
            return;
        busy = true;
        UpdateButtons();
        try
        {
            byte[] pdf = await repository.RenderSalesOrderPdfAsync(order);
            File.WriteAllBytes(pdfDialog.FileName, pdf);
            statusLabel.Text = "Sales order PDF saved.";
        }
        catch (Exception error) when (error is IOException or NpgsqlException or TimeoutException or
            InvalidOperationException or UnauthorizedAccessException)
        {
            statusLabel.Text = error is NpgsqlException or TimeoutException
                ? "The Sales order could not be loaded for PDF export." : error.Message;
        }
        finally
        {
            busy = false;
            UpdateButtons();
        }
    }

    private void DisposePdfDialog(object sender, EventArgs e) => pdfDialog.Dispose();

    private async void ReloadClicked(object sender, EventArgs e) => await RunAsync(null);
    private async void CancelClicked(object sender, EventArgs e) => await RunAsync(false);
    private async void CloseClicked(object sender, EventArgs e) => await RunAsync(true);
    private void ConfirmChanged(object sender, EventArgs e) => UpdateButtons();
    private void ArchiveReasonChanged(object sender, EventArgs e) => UpdateButtons();
    private void GuardClosing(object sender, FormClosingEventArgs e) => e.Cancel = busy;
    private async void ReviseClicked(object sender, EventArgs e)
    {
        if (repository is null || busy || revisionPreview is not { } preview)
            return;
        busy = true;
        UpdateButtons();
        try
        {
            var draft = await repository.ReviseSalesOrderAsync(preview, archiveReasonBox.Text, revisionRequest);
            RevisedOrder = draft;
            Changed = true;
            if (!IsDisposed)
                statusLabel.Text = $"Draft revision {draft.Number} created. Close this window to open it in the Sales list.";
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or InvalidOperationException or
            UnauthorizedAccessException or ArgumentException)
        {
            if (!IsDisposed)
                statusLabel.Text = error is NpgsqlException or TimeoutException ? "Could not confirm the revision. Retry the same reason."
                    : error.Message;
        }
        finally
        {
            busy = false;
            if (!IsDisposed)
                UpdateButtons();
        }
    }
    private async void ArchiveClicked(object sender, EventArgs e)
    {
        if (repository is null || busy || archivePreview is not { } preview)
            return;
        busy = true;
        UpdateButtons();
        try
        {
            await repository.ArchiveSalesOrderAsync(preview, archiveReasonBox.Text, archiveRequest);
            Changed = Archived = true;
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or InvalidOperationException or
            UnauthorizedAccessException or ArgumentException)
        {
            if (!IsDisposed)
                statusLabel.Text = error is NpgsqlException or TimeoutException ? "Could not confirm the archive. Retry the same reason."
                    : error.Message;
        }
        finally
        {
            busy = false;
            if (!IsDisposed)
                UpdateButtons();
        }
        if (Archived && !IsDisposed)
        {
            await RunAsync(null);
            if (!IsDisposed)
                statusLabel.Text = "Draft archived with its items and history retained.";
        }
    }
    private void ActivityClicked(object sender, EventArgs e)
    {
        if (repository is null || busy || overview is not { } current)
            return;
        using var history = new SalesOrderActivityForm(repository, order, current.Number);
        history.ShowDialog(this);
    }
    private void EngagementsClicked(object sender, EventArgs e)
    {
        if (repository is null || busy || overview is not { } current)
            return;
        using var engagements = new SalesEngagementsForm(repository, order, current.Number);
        engagements.ShowDialog(this);
    }
    private void ContractsClicked(object sender, EventArgs e)
    {
        if (repository is null || busy || overview is not { } current)
            return;
        using var contracts = new SalesContractsForm(repository, order, current.Number);
        contracts.ShowDialog(this);
    }
    private async void ItemsClicked(object sender, EventArgs e)
    {
        if (repository is null || busy || overview is not { } current)
            return;
        using var dialog = new SalesOrderItemsForm(repository, order, current.Number);
        dialog.ShowDialog(this);
        if (dialog.Changed && !IsDisposed)
        {
            Changed = true;
            await RunAsync(null);
        }
    }

    private async Task RunAsync(bool? close)
    {
        if (repository is null || busy || (close.HasValue && (!confirmBox.Checked || overview is null)))
            return;
        busy = true;
        UpdateButtons();
        try
        {
            if (close.HasValue && overview is { } current)
            {
                await repository.ChangeSalesOrderLifecycleAsync(order, current.Status, close.Value);
                Changed = true;
            }
            archivePreview = null;
            revisionPreview = null;
            overview = await repository.LoadSalesOrderOverviewAsync(order);
            linkedInvoice = null;
            invoiceStatusLabel.Text = "";
            try { await LoadLinkedInvoiceAsync(); }
            catch (Exception error) when (error is NpgsqlException or TimeoutException or InvalidOperationException) { }
            sourceQuotation = null;
            try { sourceQuotation = await repository.FindSourceQuotationAsync(order); }
            catch (Exception error) when (error is NpgsqlException or TimeoutException) { }
            if (overview.Status != "archived")
            {
                try { revisionPreview = await repository.LoadSalesOrderRevisionAsync(order); }
                catch (Exception error) when (error is UnauthorizedAccessException or InvalidOperationException) { }
            }
            if (overview.Status is "draft" or "created" or "planned")
            {
                try { archivePreview = await repository.LoadSalesOrderArchiveAsync(order); }
                catch (Exception error) when (error is UnauthorizedAccessException or InvalidOperationException) { }
            }
            if (IsDisposed)
                return;
            var detail = overview;
            headingLabel.Text = $"{detail.Number}   ·   {detail.Title}";
            currentStatusLabel.Text = $"Status   {detail.Status.Replace('_', ' ')}";
            customerLabel.Text = $"Customer   {detail.Customer ?? "Unavailable"}";
            scheduleLabel.Text = $"Expected schedule   {detail.Starts?.ToString("d") ?? "—"} to {detail.Ends?.ToString("d") ?? "—"}";
            totalsLabel.Text = $"{detail.Currency}   Subtotal {detail.Subtotal:N2}   Discount {detail.Discount:N2}   Tax {detail.Tax:N2}   Total {detail.Total:N2}";
            termsBox.Text = detail.Terms;
            statusLabel.Text = close is true ? "Sales order closed." : close is false ? "Sales order cancelled." : "";
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or InvalidOperationException or UnauthorizedAccessException)
        {
            overview = null;
            if (!IsDisposed)
                statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException ? error.Message :
                    "Could not load or update the Sales order. Reload before retrying.";
        }
        finally
        {
            busy = false;
            if (!IsDisposed)
            {
                confirmBox.Checked = false;
                UpdateButtons();
            }
        }
    }

    private void UpdateButtons()
    {
        reloadButton.Enabled = !busy;
        activityButton.Enabled = !busy && overview is not null;
        pdfButton.Enabled = !busy && overview is not null;
        purchaseHistoryButton.Enabled = !busy && overview?.Customer is not null;
        linkedInvoiceButton.Enabled = !busy && overview is not null && linkedInvoice is not null;
        sourceQuotationButton.Enabled = !busy && overview is not null && sourceQuotation is not null;
        engagementsButton.Enabled = !busy && overview is not null;
        contractsButton.Enabled = !busy && overview is not null;
        archiveReasonBox.Enabled = !busy && (archivePreview is not null || revisionPreview is not null);
        bool reasonReady = archiveReasonBox.Enabled && archiveReasonBox.Text.Trim().Length >= 5;
        archiveButton.Enabled = reasonReady && archivePreview is not null && RevisedOrder is null;
        reviseButton.Enabled = reasonReady && revisionPreview is not null && RevisedOrder is null;
        itemsButton.Enabled = !busy && overview?.Status is "draft" or "pending_approval";
        confirmBox.Enabled = !busy && overview?.CanCancel == true;
        cancelOrderButton.Enabled = !busy && confirmBox.Checked && overview?.CanCancel == true;
        closeOrderButton.Enabled = !busy && confirmBox.Checked && overview?.CanClose == true;
    }
}
