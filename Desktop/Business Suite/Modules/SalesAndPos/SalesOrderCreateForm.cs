using System.ComponentModel;
using System.Globalization;
using Npgsql;
using Telerik.WinControls.UI;
using PositionChangedEventArgs = Telerik.WinControls.UI.Data.PositionChangedEventArgs;

namespace Business_Suite;

internal sealed record SalesOrderDraftRow(SalesCatalogItem Item, SalesOrderInputLine Line, string Currency, decimal Total)
{
    public string Code => Item.Code;
    public string Name => Item.Name;
    public decimal Quantity => Line.Quantity;
    public decimal UnitPrice => Line.UnitPrice;
    public decimal Discount => Line.DiscountRate;
    public decimal Tax => Line.TaxRate;
}

public sealed partial class SalesOrderCreateForm : Form
{
    private readonly SalesOrderRepository? repository;
    private readonly Guid request = Guid.NewGuid();
    private readonly BindingList<SalesOrderDraftRow> rows = new BindingList<SalesOrderDraftRow>();
    private List<SalesCatalogItem> catalog = new List<SalesCatalogItem>();
    private bool busy;

    internal SalesOrderCreated? SavedOrder { get; private set; }

    public SalesOrderCreateForm()
    {
        InitializeComponent();
    }

    internal SalesOrderCreateForm(SalesOrderRepository repository) : this()
    {
        this.repository = repository;
    }

    private async void LoadForm(object sender, EventArgs e)
    {
        if (repository is null)
            return;
        linesGrid.DataSource = rows;
        await RunAsync(async () =>
        {
            currencyBox.Text = await repository.SalesOrderCurrencyAsync();
            await LoadCustomersAsync();
            await LoadCatalogAsync();
        });
    }

    private async void FindCustomer(object sender, EventArgs e) => await RunAsync(LoadCustomersAsync);

    private async Task LoadCustomersAsync()
    {
        if (repository is null)
            return;
        var result = await repository.SalesCustomersAsync(customerSearchBox.Text);
        customerList.DisplayMember = nameof(SalesCustomer.Name);
        customerList.DataSource = result;
        customerList.SelectedIndex = -1;
        if (result.Count == 0)
            statusLabel.Text = "No shared customers match the search.";
    }

    private async void FindCatalog(object sender, EventArgs e) => await RunAsync(LoadCatalogAsync);

    private async Task LoadCatalogAsync()
    {
        if (repository is null)
            return;
        catalog = await repository.SalesCatalogAsync(catalogSearchBox.Text);
        BindCatalog(catalog);
        if (catalog.Count == 0)
            statusLabel.Text = "No active products or services match the search.";
    }

    private void BindCatalog(List<SalesCatalogItem> items)
    {
        catalogList.DisplayMember = nameof(SalesCatalogItem.Display);
        catalogList.DataSource = items;
        catalogList.SelectedIndex = -1;
    }

    private void CatalogChanged(object sender, PositionChangedEventArgs e) => BindPrices();
    private void CurrencyChanged(object sender, EventArgs e)
    {
        BindPrices();
        UpdateTotal();
    }

    private void BindPrices()
    {
        if (catalogList is null || priceList is null || currencyBox is null)
            return;
        string currency = currencyBox.Text.Trim().ToUpperInvariant();
        var item = catalogList.SelectedItem?.DataBoundItem as SalesCatalogItem;
        priceList.DisplayMember = nameof(SalesCatalogPrice.Display);
        priceList.DataSource = item?.Prices.Where(price => price.Currency == currency).ToList()
            ?? new List<SalesCatalogPrice>();
        taxBox.Text = item?.Tax.ToString("0.##", CultureInfo.CurrentCulture) ?? "0";
    }

    private void PriceChanged(object sender, PositionChangedEventArgs e)
    {
        if (unitBox is not null)
            unitBox.Text = (priceList.SelectedItem?.DataBoundItem as SalesCatalogPrice)?.Price
                .ToString("F2", CultureInfo.CurrentCulture) ?? "";
    }

    private void DateChanged(object sender, EventArgs e)
    {
        startDate.Enabled = startCheck.Checked;
        endDate.Enabled = endCheck.Checked;
    }

    private void AddLine(object sender, EventArgs e)
    {
        if (catalogList.SelectedItem?.DataBoundItem is not SalesCatalogItem item ||
            priceList.SelectedItem?.DataBoundItem is not SalesCatalogPrice price)
        {
            statusLabel.Text = "Choose a catalog item priced in the selected currency.";
            return;
        }
        try
        {
            var line = new SalesOrderInputLine(item.Id, item.Revision, price.Id, ParseDecimal(quantityBox, "quantity"),
                ParseDecimal(unitBox, "unit price"), ParseDecimal(discountBox, "discount"), ParseDecimal(taxBox, "tax"));
            var amounts = SalesOrderRepository.CalculateLine(line);
            var existing = rows.FirstOrDefault(row => row.Item.Id == item.Id);
            var updated = new SalesOrderDraftRow(item, line, price.Currency, amounts.Total);
            if (existing is null)
                rows.Add(updated);
            else
                rows[rows.IndexOf(existing)] = updated;
            statusLabel.Text = "";
            UpdateTotal();
        }
        catch (ArgumentException error)
        {
            statusLabel.Text = error.Message;
        }
    }

    private void SelectLine(object sender, GridViewCellEventArgs e)
    {
        if (e.Row?.DataBoundItem is not SalesOrderDraftRow row)
            return;
        if (!catalog.Any(item => item.Id == row.Item.Id))
            BindCatalog(catalog.Concat(new[] { row.Item }).ToList());
        catalogList.SelectedItem = catalogList.Items.FirstOrDefault(item => (item.DataBoundItem as SalesCatalogItem)?.Id == row.Item.Id);
        priceList.SelectedItem = priceList.Items.FirstOrDefault(price => (price.DataBoundItem as SalesCatalogPrice)?.Id == row.Line.PricingId);
        quantityBox.Text = row.Line.Quantity.ToString("0.##", CultureInfo.CurrentCulture);
        unitBox.Text = row.Line.UnitPrice.ToString("F2", CultureInfo.CurrentCulture);
        discountBox.Text = row.Line.DiscountRate.ToString("0.##", CultureInfo.CurrentCulture);
        taxBox.Text = row.Line.TaxRate.ToString("0.##", CultureInfo.CurrentCulture);
    }

    private void RemoveLine(object sender, EventArgs e)
    {
        if (linesGrid.CurrentRow?.DataBoundItem is SalesOrderDraftRow row)
            rows.Remove(row);
        UpdateTotal();
    }

    private void UpdateTotal()
    {
        if (totalLabel is null || currencyBox is null)
            return;
        string currency = currencyBox.Text.Trim().ToUpperInvariant();
        totalLabel.Text = rows.Any(row => row.Currency != currency)
            ? "Some order items are priced in a different currency."
            : $"Order total including tax  {currency} {rows.Sum(row => row.Total):N2}";
    }

    private async void SaveClicked(object sender, EventArgs e)
    {
        if (repository is null || busy)
            return;
        string currency = currencyBox.Text.Trim().ToUpperInvariant();
        if (rows.Any(row => row.Currency != currency))
        {
            statusLabel.Text = "Choose prices in the order currency for every item.";
            return;
        }
        await RunAsync(async () =>
        {
            var draft = new SalesOrderDraft(request, titleBox.Text.Trim(),
                (customerList.SelectedItem?.DataBoundItem as SalesCustomer)?.Id ?? 0, currency,
                startCheck.Checked ? startDate.Value.Date : null, endCheck.Checked ? endDate.Value.Date : null,
                termsBox.Text, rows.Select(row => row.Line).ToArray());
            SavedOrder = await repository.CreateSalesOrderAsync(draft);
            DialogResult = DialogResult.OK;
        });
    }

    private async Task RunAsync(Func<Task> operation)
    {
        if (busy)
            return;
        busy = true;
        saveButton.Enabled = findCustomerButton.Enabled = findCatalogButton.Enabled = cancelButton.Enabled = false;
        statusLabel.Text = "";
        try
        {
            await operation();
        }
        catch (Exception error) when (error is ArgumentException or InvalidOperationException or
            UnauthorizedAccessException or NpgsqlException or TimeoutException)
        {
            statusLabel.Text = error is NpgsqlException or TimeoutException
                ? "Could not confirm the request. Check database connectivity and retry with the same draft."
                : error.Message;
        }
        finally
        {
            busy = false;
            if (!IsDisposed)
                saveButton.Enabled = findCustomerButton.Enabled = findCatalogButton.Enabled = cancelButton.Enabled = true;
        }
    }

    private void OrderFormClosing(object sender, FormClosingEventArgs e)
    {
        if (busy && DialogResult != DialogResult.OK)
            e.Cancel = true;
    }

    private static decimal ParseDecimal(RadTextBox box, string name) =>
        decimal.TryParse(box.Text, NumberStyles.Number, CultureInfo.CurrentCulture, out decimal value)
            ? value : throw new ArgumentException($"Enter a valid {name}.");
}
