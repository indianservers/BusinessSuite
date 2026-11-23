using Npgsql;

namespace Business_Suite;

public sealed partial class SalesInvoicePaymentForm : Form
{
    private readonly SalesOrderRepository? repository;
    private readonly int orderId;
    private readonly int invoiceId;
    private readonly SalesMilestoneInvoiceLink? milestone;
    private FileStream? journalLock;
    private SalesIntentJournal<SalesPaymentIntent>? journal;
    private SalesPaymentIntent? pending;
    private bool saving;
    internal SalesPaymentResult? SavedPayment { get; private set; }

    public SalesInvoicePaymentForm() => InitializeComponent();

    internal SalesInvoicePaymentForm(SalesOrderRepository repository, int order, LinkedSalesInvoice invoice, decimal balance,
        SalesMilestoneInvoiceLink? milestone = null) : this()
    {
        this.repository = repository;
        orderId = order;
        invoiceId = invoice.Id;
        this.milestone = milestone;
        headingLabel.Text = $"Record payment for {invoice.Number}";
        balanceLabel.Text = $"Outstanding {invoice.Currency} {balance:N2}";
    }

    private void PaymentShown(object sender, EventArgs e)
    {
        if (repository is null)
            return;
        methodPicker.DataSource = new[]
        {
            new { Name = "Bank transfer", Key = "bank_transfer" }, new { Name = "UPI", Key = "upi" },
            new { Name = "Cash", Key = "cash" }, new { Name = "Card", Key = "card" },
            new { Name = "Cheque", Key = "cheque" }
        };
        methodPicker.DisplayMember = "Name";
        methodPicker.ValueMember = "Key";
        methodPicker.SelectedIndex = 0;
        datePicker.Value = DateTime.Today;
        try
        {
            journal = repository.PaymentJournal(invoiceId);
            journalLock = journal.Acquire();
            pending = journal.Read();
            if (pending is not null)
            {
                amountEditor.Value = pending.Amount;
                methodPicker.SelectedValue = pending.Method;
                datePicker.Value = pending.ReceiptDate;
                referenceBox.Text = pending.Reference;
                statusLabel.Text = "Resolve the saved payment before recording another.";
            }
            ApplyState();
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException or InvalidOperationException)
        {
            statusLabel.Text = error is InvalidOperationException ? error.Message
                : "The recovery folder is unavailable or another window owns this payment.";
            saveButton.Enabled = false;
        }
    }

    private async void SaveClicked(object sender, EventArgs e)
    {
        if (repository is null || journal is null || journalLock is null || saving)
            return;
        saving = true;
        ApplyState();
        try
        {
            if (pending is null)
            {
                var intent = new SalesPaymentIntent(Guid.NewGuid(), amountEditor.Value, referenceBox.Text,
                    methodPicker.SelectedValue as string ?? "", datePicker.Value.Date);
                journal.Save(intent);
                pending = intent;
            }
            statusLabel.Text = "Recording received payment…";
            var result = milestone is null ? await repository.RecordSalesPaymentAsync(orderId, invoiceId, pending)
                : await repository.RecordSalesMilestonePaymentAsync(orderId, invoiceId, pending, milestone);
            journal.Clear();
            pending = null;
            SavedPayment = result;
            DialogResult = DialogResult.OK;
        }
        catch (SalesPaymentRejectedException error)
        {
            try
            {
                journal.Clear();
                pending = null;
                statusLabel.Text = error.Message;
            }
            catch (Exception io) when (io is IOException or UnauthorizedAccessException)
            {
                statusLabel.Text = "Payment was rejected. Recovery storage could not be cleared.";
            }
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or InvalidOperationException
            or UnauthorizedAccessException or IOException or ArgumentException)
        {
            statusLabel.Text = error is ArgumentException or UnauthorizedAccessException or InvalidOperationException ? error.Message
                : pending is null ? "Could not write payment recovery information. No payment request was sent."
                : "Payment outcome is uncertain. Retry the same saved payment.";
        }
        finally
        {
            saving = false;
            if (!IsDisposed)
                ApplyState();
        }
    }

    private void ApplyState()
    {
        bool editable = !saving && pending is null;
        amountEditor.Enabled = referenceBox.Enabled = methodPicker.Enabled = datePicker.Enabled = editable;
        saveButton.Text = pending is null ? "Record received payment" : "Retry same payment";
        saveButton.Enabled = !saving && journalLock is not null;
        cancelButton.Enabled = !saving;
    }

    private void PaymentClosing(object sender, FormClosingEventArgs e)
    {
        if (saving && DialogResult != DialogResult.OK)
            e.Cancel = true;
    }

    private void PaymentClosed(object sender, FormClosedEventArgs e) => journalLock?.Dispose();
}
