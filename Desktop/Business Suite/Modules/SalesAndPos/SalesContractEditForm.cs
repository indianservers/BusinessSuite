using Npgsql;

namespace Business_Suite;

public sealed partial class SalesContractEditForm : Form
{
    private readonly SalesOrderRepository? repository;
    private readonly int order;
    private readonly SalesContractRow? original;
    private readonly bool creating;
    private readonly Guid request = Guid.NewGuid();
    private bool saving;

    public SalesContractEditForm() => InitializeComponent();
    internal SalesContractEditForm(SalesOrderRepository repository, int order, SalesContractRow contract) : this()
    {
        this.repository = repository;
        this.order = order;
        original = contract;
        Text = $"Edit contract {contract.Number}";
        numberBox.Text = contract.Number;
        titleBox.Text = contract.Title;
        typeBox.Text = contract.Kind;
        currencyBox.Text = contract.Currency;
        amountBox.Value = contract.Value;
        effectiveCheck.Checked = contract.Effective.HasValue;
        expiryCheck.Checked = contract.Expiry.HasValue;
        if (contract.Effective is DateTime effective)
            effectivePicker.Value = effective;
        if (contract.Expiry is DateTime expiry)
            expiryPicker.Value = expiry;
        termsBox.Text = contract.Terms;
        UpdateButtons();
    }

    internal SalesContractEditForm(SalesOrderRepository repository, int order, SalesOrderOverview source) : this()
    {
        this.repository = repository;
        this.order = order;
        creating = true;
        Text = $"Create contract for {source.Number}";
        titleBox.Text = source.Title;
        typeBox.Text = "services";
        currencyBox.Text = source.Currency;
        amountBox.Value = source.Total;
        saveButton.Text = "Create contract";
        numberLabel.Text = "Number (optional)";
        UpdateButtons();
    }

    private void DateChanged(object sender, EventArgs e) => UpdateButtons();
    private void GuardClosing(object sender, FormClosingEventArgs e) => e.Cancel = saving && DialogResult != DialogResult.OK;

    private async void SaveClicked(object sender, EventArgs e)
    {
        if (repository is null || (!creating && original is null) || saving)
            return;
        var change = new SalesContractChanges(titleBox.Text, typeBox.Text, currencyBox.Text, amountBox.Value,
            effectiveCheck.Checked ? effectivePicker.Value.Date : null, expiryCheck.Checked ? expiryPicker.Value.Date : null,
            termsBox.Text);
        saving = true;
        UpdateButtons();
        try
        {
            if (creating)
                await repository.CreateSalesContractAsync(order, change, numberBox.Text, request);
            else if (original is not null)
                await repository.EditSalesContractAsync(order, original, change, request);
            DialogResult = DialogResult.OK;
        }
        catch (Exception error) when (error is ArgumentException or UnauthorizedAccessException or InvalidOperationException
            or NpgsqlException or TimeoutException)
        {
            if (!IsDisposed)
                statusLabel.Text = error is NpgsqlException or TimeoutException
                    ? "Could not confirm the save. Retry the same values or reopen the contract list."
                    : error.Message;
        }
        finally
        {
            saving = false;
            if (!IsDisposed)
                UpdateButtons();
        }
    }

    private void UpdateButtons()
    {
        if (saveButton is null)
            return;
        bool enabled = !saving && (creating || original is not null);
        titleBox.Enabled = typeBox.Enabled = currencyBox.Enabled = amountBox.Enabled = termsBox.Enabled = enabled;
        effectiveCheck.Enabled = expiryCheck.Enabled = enabled;
        effectivePicker.Enabled = enabled && effectiveCheck.Checked;
        expiryPicker.Enabled = enabled && expiryCheck.Checked;
        saveButton.Enabled = enabled;
        numberBox.ReadOnly = !creating || saving;
    }
}
