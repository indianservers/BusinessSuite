namespace Business_Suite;

public sealed partial class PosSplitTenderForm : Form
{
    private sealed record MethodChoice(string Label, string Code);
    private sealed record TenderRow(PosTenderPart Part, string MethodLabel)
    {
        public decimal Amount => Part.Amount;
        public string? Reference => Part.Reference;
    }

    private readonly List<TenderRow> rows = new();
    private readonly decimal total;
    private readonly string currency = "";
    private readonly bool requiresFullPayment;
    internal IReadOnlyList<PosTenderPart>? SavedPayments { get; private set; }

    public PosSplitTenderForm() => InitializeComponent();

    internal PosSplitTenderForm(decimal total, string currency, bool requiresFullPayment) : this()
    {
        this.total = total;
        this.currency = currency;
        this.requiresFullPayment = requiresFullPayment;
        var methods = new List<MethodChoice>
        {
            new MethodChoice("Cash", "cash"), new MethodChoice("Card", "card"),
            new MethodChoice("UPI", "upi"), new MethodChoice("Bank transfer", "bank_transfer")
        };
        if (!requiresFullPayment)
            methods.Add(new MethodChoice("Credit", "credit"));
        methodPicker.DataSource = methods;
        methodPicker.DisplayMember = "Label";
        methodPicker.ValueMember = "Code";
        methodPicker.SelectedIndex = 0;
        RefreshSummary();
    }

    private void AddClicked(object sender, EventArgs e)
    {
        if (rows.Count >= 10 || methodPicker.SelectedItem?.DataBoundItem is not MethodChoice method)
            return;
        if (amountEditor.Value <= 0)
        {
            statusLabel.Text = "Enter a positive amount.";
            return;
        }
        string reference = referenceBox.Text.Trim();
        var part = new PosTenderPart(Guid.NewGuid(), method.Code, amountEditor.Value,
            method.Code == "credit" || reference.Length == 0 ? null : reference);
        rows.Add(new TenderRow(part, method.Label));
        amountEditor.Value = 0;
        referenceBox.Clear();
        RefreshSummary();
    }

    private void RemoveClicked(object sender, EventArgs e)
    {
        if (paymentGrid.CurrentRow?.DataBoundItem is TenderRow selected)
        {
            rows.Remove(selected);
            RefreshSummary();
        }
    }

    private void MethodChanged(object sender, EventArgs e) =>
        referenceBox.Enabled = methodPicker.SelectedValue is string mode && mode != "credit";

    private void SelectionChanged(object sender, EventArgs e) =>
        removeButton.Enabled = paymentGrid.CurrentRow?.DataBoundItem is TenderRow;

    private void RefreshSummary()
    {
        paymentGrid.DataSource = rows.ToList();
        addButton.Enabled = rows.Count < 10;
        summaryLabel.Text = $"Bill total {currency} {total:N2}";
        confirmButton.Enabled = false;
        if (rows.Count == 0)
        {
            statusLabel.Text = requiresFullPayment ? "Enter received payments to cover the full bill."
                : "Enter cash or another received payment. Add Credit for any unpaid remainder.";
            return;
        }
        try
        {
            var allocation = SalesOrderRepository.AllocatePosSplitTender(total, rows.Select(row => row.Part).ToList(), requiresFullPayment);
            statusLabel.Text = $"Received {currency} {allocation.Paid:N2} · Outstanding {total - allocation.Paid:N2} · Change {allocation.Change:N2}";
            confirmButton.Enabled = true;
        }
        catch (ArgumentException error)
        {
            statusLabel.Text = error.Message;
        }
    }

    private void ConfirmClicked(object sender, EventArgs e)
    {
        if (!confirmButton.Enabled)
            return;
        SavedPayments = rows.Select(row => row.Part).ToList();
        DialogResult = DialogResult.OK;
    }
}
