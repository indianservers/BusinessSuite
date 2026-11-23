namespace Business_Suite;

public sealed partial class PosCashCheckoutForm : Form
{
    private sealed record TenderOption(string Label, string Code);
    private readonly bool requiresFullPayment;

    public PosCashCheckoutForm() => InitializeComponent();

    internal PosCashCheckoutForm(string customer, string currency, decimal total, bool walkIn, bool canCollect, bool canCredit) : this()
    {
        customerLabel.Text = $"Customer · {customer}";
        totalLabel.Text = $"{currency} {total:N2}";
        requiresFullPayment = walkIn;
        var methods = new List<TenderOption>();
        if (canCollect)
        {
            methods.Add(new TenderOption("Cash", "cash"));
            methods.Add(new TenderOption("Card", "card"));
            methods.Add(new TenderOption("UPI", "upi"));
            methods.Add(new TenderOption("Bank transfer", "bank_transfer"));
            methods.Add(new TenderOption("Split payment", "split"));
        }
        if (!walkIn && canCredit)
            methods.Add(new TenderOption("Credit", "credit"));
        methodPicker.DataSource = methods;
        methodPicker.DisplayMember = "Label";
        methodPicker.ValueMember = "Code";
        methodPicker.SelectedIndex = 0;
        methodPicker.Enabled = methods.Count > 1;
        UpdateMethod();
    }

    internal string? Tender => methodPicker.SelectedValue is string method && method != "cash" ? method : null;
    internal string? Reference => Tender is not ("credit" or "split") && referenceBox.Text.Trim() is { Length: > 0 } reference ? reference : null;

    private void TenderChanged(object sender, EventArgs e) => UpdateMethod();

    private void UpdateMethod()
    {
        if (methodPicker.SelectedValue is not string selected)
            return;
        instructionsLabel.Text = selected switch
        {
            "credit" => "Issue an invoice with the full balance due for this customer.",
            "split" when requiresFullPayment => "Combine received payments to cover the full bill. Only cash can include change.",
            "split" => "Combine received methods and any explicit credit. Only cash can include change.",
            _ => "Confirm the store has already received this payment."
        };
        confirmButton.Text = selected switch
        {
            "credit" => "Issue unpaid invoice",
            "split" => "Enter split payments",
            _ => "Confirm payment received"
        };
        referenceBox.Enabled = selected is not ("credit" or "split");
    }
}
