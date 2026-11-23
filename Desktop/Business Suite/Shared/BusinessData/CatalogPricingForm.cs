using Telerik.WinControls.UI;

namespace Business_Suite;

public sealed partial class CatalogPricingForm : Form
{
    private static readonly string[] Intervals = { "once", "day", "week", "month", "year" };
    private readonly List<CatalogPriceOption> prices = new();
    private readonly string baseCurrency = "INR";
    private readonly decimal baseAmount;
    private string? editing;
    private bool binding;

    public CatalogPricingForm() => InitializeComponent();

    internal CatalogPricingForm(CatalogPriceOption[] initial, string currency, decimal amount) : this()
    {
        prices.AddRange(initial);
        baseCurrency = currency;
        baseAmount = amount;
        BindPrices();
    }

    internal CatalogPriceOption[] Prices => prices.ToArray();
    internal bool Changed { get; private set; }

    private void BindPrices()
    {
        binding = true;
        pricesGrid.DataSource = prices.ToArray();
        pricesGrid.CurrentRow = null;
        binding = false;
        StartNew();
    }

    private void StartNew()
    {
        editing = null;
        priceName.Text = "";
        priceAmount.Value = baseAmount;
        priceCurrency.Text = baseCurrency;
        intervalBox.SelectedIndex = 0;
        removeButton.Enabled = false;
        feedback.Text = prices.Count == 0 ? "The base price applies until an additional price is saved." : "";
    }

    private void AddClicked(object? sender, EventArgs e)
    {
        pricesGrid.CurrentRow = null;
        StartNew();
        priceName.Focus();
    }

    private void SelectionChanged(object? sender, EventArgs e)
    {
        if (binding || intervalBox is null || pricesGrid.CurrentRow?.DataBoundItem is not CatalogPriceOption row)
            return;
        editing = row.Id;
        priceName.Text = row.Name;
        priceAmount.Value = row.Amount;
        priceCurrency.Text = row.Currency;
        intervalBox.SelectedIndex = Array.IndexOf(Intervals, row.Interval);
        removeButton.Enabled = true;
        feedback.Text = "";
    }

    private void ApplyClicked(object? sender, EventArgs e)
    {
        var price = new CatalogPriceOption(editing ?? Guid.NewGuid().ToString("N"), priceName.Text.Trim(),
            priceAmount.Value, priceCurrency.Text.Trim().ToUpperInvariant(),
            intervalBox.SelectedIndex < 0 ? "" : Intervals[intervalBox.SelectedIndex]);
        int index = prices.FindIndex(item => item.Id == price.Id);
        var proposed = prices.ToList();
        if (index < 0)
            proposed.Add(price);
        else
            proposed[index] = price;
        try
        {
            SharedCatalogRepository.ValidateAdditionalPrices(proposed.ToArray());
            prices.Clear();
            prices.AddRange(proposed);
            Changed = true;
            BindPrices();
            pricesGrid.CurrentRow = pricesGrid.Rows.OfType<GridViewDataRowInfo>()
                .FirstOrDefault(row => (row.DataBoundItem as CatalogPriceOption)?.Id == price.Id);
            feedback.Text = "Price updated in this draft.";
        }
        catch (ArgumentException error)
        {
            feedback.Text = error.Message;
        }
    }

    private void RemoveClicked(object? sender, EventArgs e)
    {
        if (editing is null || prices.RemoveAll(price => price.Id == editing) == 0)
            return;
        Changed = true;
        BindPrices();
    }

    private void DoneClicked(object? sender, EventArgs e) => DialogResult = DialogResult.OK;
}
