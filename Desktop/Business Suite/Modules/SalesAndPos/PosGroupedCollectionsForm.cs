using Npgsql;

namespace Business_Suite;

public sealed partial class PosGroupedCollectionsForm : Form
{
    private readonly SalesOrderRepository? repository;
    private SalesIntentJournal<PosLaterPaymentIntent>? journal;
    private FileStream? lease;
    private PosLaterPaymentIntent? pending;
    private PosCollectionList? source;
    private bool busy;

    public PosGroupedCollectionsForm() => InitializeComponent();
    internal PosGroupedCollectionsForm(SalesOrderRepository repository) : this() => this.repository = repository;

    private async void CollectionsShown(object sender, EventArgs e)
    {
        if (repository is null)
            return;
        methodPicker.DataSource = new[]
        {
            new { Label = "Cash", Code = "cash" }, new { Label = "Card", Code = "card" },
            new { Label = "UPI", Code = "upi" }, new { Label = "Bank transfer", Code = "bank_transfer" }
        };
        methodPicker.DisplayMember = "Label";
        methodPicker.ValueMember = "Code";
        methodPicker.SelectedIndex = 0;
        try
        {
            journal = repository.PosCollectionJournal();
            lease = journal.Acquire();
            pending = journal.Read();
            if (pending is not null)
            {
                amountEditor.Value = pending.Amount;
                methodPicker.SelectedValue = pending.Method;
                referenceBox.Text = pending.Reference ?? "";
            }
            await LoadAsync();
        }
        catch (Exception error) when (error is IOException or InvalidOperationException or UnauthorizedAccessException)
        {
            statusLabel.Text = error is InvalidOperationException ? error.Message
                : "The payment recovery folder is unavailable or another window owns it.";
        }
    }

    private async void RefreshClicked(object sender, EventArgs e) => await LoadAsync();

    private async Task LoadAsync(string? message = null)
    {
        if (repository is null || busy || lease is null)
            return;
        busy = true;
        ApplyState();
        try
        {
            source = await repository.ListGroupedPosOutstandingAsync(searchBox.Text);
            headingLabel.Text = $"{source.Register} · POS invoice payments · {source.Currency}";
            invoiceGrid.DataSource = source.Invoices;
            statusLabel.Text = message ?? (pending is not null ? $"Resolve the saved payment of {pending.Amount:N2} before starting another."
                : source.Invoices.Count == 0 ? "No outstanding POS invoices match the search." : "");
        }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException or NpgsqlException or TimeoutException)
        {
            source = null;
            invoiceGrid.DataSource = null;
            statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException ? error.Message
                : "Could not load POS invoices. Check PostgreSQL connectivity and refresh.";
        }
        finally
        {
            busy = false;
            ApplyState();
        }
    }

    private void InvoiceSelectionChanged(object sender, EventArgs e) => ApplyState();

    private void ApplyState()
    {
        bool editable = !busy && pending is null && source is not null;
        amountEditor.Enabled = methodPicker.Enabled = referenceBox.Enabled = editable;
        invoiceGrid.Enabled = !busy && pending is null;
        recordButton.Text = pending is null ? "Record payment" : "Retry same payment";
        recordButton.Enabled = !busy && lease is not null
            && (pending is not null || editable && invoiceGrid.CurrentRow?.DataBoundItem is PosOutstandingInvoice);
        refreshButton.Enabled = closeButton.Enabled = !busy;
    }

    private async void RecordClicked(object sender, EventArgs e)
    {
        if (repository is null || journal is null || lease is null || busy || !recordButton.Enabled)
            return;
        busy = true;
        ApplyState();
        string? message = null;
        try
        {
            if (pending is null)
            {
                if (source is null || invoiceGrid.CurrentRow?.DataBoundItem is not PosOutstandingInvoice selected)
                    return;
                if (amountEditor.Value <= 0 || amountEditor.Value > selected.Outstanding)
                    throw new ArgumentException($"Enter an amount up to {selected.Currency} {selected.Outstanding:N2}.");
                var reference = referenceBox.Text.Trim();
                var intent = new PosLaterPaymentIntent(Guid.NewGuid(), selected.CheckoutId, selected.Revision, source.SessionId,
                    methodPicker.SelectedValue as string ?? "", amountEditor.Value, reference.Length == 0 ? null : reference);
                journal.Save(intent);
                pending = intent;
            }
            statusLabel.Text = "Recording received payment…";
            var saved = await repository.CollectGroupedPosPaymentAsync(pending);
            journal.Clear();
            pending = null;
            amountEditor.Value = 0;
            referenceBox.Clear();
            message = $"Receipt {saved.Receipt} saved · Outstanding {saved.Outstanding:N2}.";
        }
        catch (PosCheckoutRejectedException error)
        {
            try
            {
                journal.Clear();
                pending = null;
                statusLabel.Text = error.Message;
            }
            catch (Exception storage) when (storage is IOException or UnauthorizedAccessException)
            {
                statusLabel.Text = "Payment was rejected. Recovery storage could not be cleared.";
            }
        }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException or NpgsqlException
            or TimeoutException or IOException or ArgumentException)
        {
            statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException or ArgumentException ? error.Message
                : pending is null ? "Could not save payment recovery information. No request was sent."
                : "Payment outcome is uncertain. Retry the same saved payment.";
        }
        finally
        {
            busy = false;
            ApplyState();
        }
        if (message is not null)
            await LoadAsync(message);
    }

    private void CollectionsClosing(object sender, FormClosingEventArgs e) => e.Cancel = busy;
    private void CollectionsClosed(object sender, FormClosedEventArgs e) => lease?.Dispose();
}
