using System.Globalization;
using Npgsql;

namespace Business_Suite;

public sealed partial class SalesOrderAddItemForm : Form
{
    private readonly SalesOrderRepository? repository;
    private readonly int order;
    private readonly Guid request = Guid.NewGuid();
    private SalesOrderItemsSnapshot? snapshot;
    private bool working;
    private Func<Task<int>>? retryAdd;

    private void ManualChanged(object sender, EventArgs e) => UpdateButtons();

    public SalesOrderAddItemForm() => InitializeComponent();
    internal SalesOrderAddItemForm(SalesOrderRepository repository, int order) : this()
    {
        this.repository = repository;
        this.order = order;
    }

    private async void FormShown(object sender, EventArgs e) => await SearchAsync();
    private async void FindClicked(object sender, EventArgs e) => await SearchAsync();
    private void CatalogChanged(object sender, EventArgs e)
    {
        if (priceList is null || taxBox is null)
            return;
        var item = catalogList.SelectedItem?.DataBoundItem as SalesCatalogItem;
        priceList.DisplayMember = nameof(SalesCatalogPrice.Display);
        priceList.DataSource = item?.Prices.Where(price => price.Currency == snapshot?.Currency).ToList()
            ?? new List<SalesCatalogPrice>();
        taxBox.Text = item?.Tax.ToString("0.##", CultureInfo.CurrentCulture) ?? "0";
        UpdateButtons();
    }

    private void PriceChanged(object sender, EventArgs e)
    {
        if (unitBox is null || manualBox?.Checked == true)
            return;
        unitBox.Text = (priceList.SelectedItem?.DataBoundItem as SalesCatalogPrice)?.Price.ToString("F2", CultureInfo.CurrentCulture) ?? "";
        UpdateButtons();
    }

    private async Task SearchAsync()
    {
        if (repository is null || working || retryAdd is not null)
            return;
        working = true;
        UpdateButtons();
        try
        {
            snapshot ??= await repository.LoadSalesOrderItemsSnapshotAsync(order);
            var catalog = await repository.SalesCatalogAsync(searchBox.Text);
            if (IsDisposed)
                return;
            headingLabel.Text = $"Add sales item · {snapshot.Currency}";
            catalogList.DisplayMember = nameof(SalesCatalogItem.Display);
            catalogList.DataSource = catalog;
            catalogList.SelectedIndex = -1;
            statusLabel.Text = catalog.Count == 0 ? "No active products or services match the search." : "";
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException or InvalidOperationException)
        {
            if (!IsDisposed)
                statusLabel.Text = error is NpgsqlException or TimeoutException ? "Could not load the Sales order or catalog." : error.Message;
        }
        finally
        {
            working = false;
            if (!IsDisposed)
                UpdateButtons();
        }
    }

    private async void AddClicked(object sender, EventArgs e)
    {
        if (repository is null || snapshot is null || working)
            return;
        working = true;
        UpdateButtons();
        try
        {
            retryAdd ??= BuildAdd(repository, snapshot);
            await retryAdd();
            DialogResult = DialogResult.OK;
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or InvalidOperationException or
            UnauthorizedAccessException or ArgumentException)
        {
            if (error is PostgresException || error is not (NpgsqlException or TimeoutException))
                retryAdd = null;
            if (!IsDisposed)
                statusLabel.Text = retryAdd is null ? error.Message : "Could not confirm the result. Retry the same item or reopen the order.";
        }
        finally
        {
            working = false;
            if (!IsDisposed)
                UpdateButtons();
        }
    }

    private Func<Task<int>> BuildAdd(SalesOrderRepository repo, SalesOrderItemsSnapshot version)
    {
        if (!manualBox.Checked)
        {
            var catalogLine = ReadSelection();
            return () => repo.AddSalesOrderLineAsync(order, version, catalogLine, request);
        }

        string description = manualDescriptionBox.Text;
        string code = manualCodeBox.Text;
        decimal quantity = ParseNumber(quantityBox.Text, "quantity");
        decimal price = ParseNumber(unitBox.Text, "unit price");
        decimal discount = ParseNumber(discountBox.Text, "discount rate");
        decimal tax = ParseNumber(taxBox.Text, "tax rate");
        return () => repo.AddManualSalesServiceAsync(order, version, description, code, quantity, price, discount, tax, request);
    }

    private SalesOrderInputLine ReadSelection()
    {
        if (catalogList.SelectedItem?.DataBoundItem is not SalesCatalogItem item ||
            priceList.SelectedItem?.DataBoundItem is not SalesCatalogPrice price)
            throw new ArgumentException("Choose a catalog item priced in the order currency.");
        return new SalesOrderInputLine(item.Id, item.Revision, price.Id, ParseNumber(quantityBox.Text, "quantity"),
            ParseNumber(unitBox.Text, "unit price"), ParseNumber(discountBox.Text, "discount rate"), ParseNumber(taxBox.Text, "tax rate"));
    }

    private static decimal ParseNumber(string text, string label) =>
        decimal.TryParse(text, NumberStyles.Number, CultureInfo.CurrentCulture, out decimal value) ? value
            : throw new ArgumentException($"Enter a valid {label}.");

    private void UpdateButtons()
    {
        if (searchButton is null || addButton is null)
            return;
        bool canEdit = !working && retryAdd is null;
        if (manualBox is null)
            return;
        bool manual = manualBox.Checked;
        manualPanel.Visible = manual;
        searchButton.Visible = searchBox.Visible = catalogList.Visible = priceList.Visible = catalogLabel.Visible = priceLabel.Visible = !manual;
        manualBox.Enabled = manualPanel.Enabled = canEdit;
        searchButton.Enabled = searchBox.Enabled = catalogList.Enabled = priceList.Enabled = canEdit && !manual;
        quantityBox.Enabled = unitBox.Enabled = discountBox.Enabled = taxBox.Enabled = canEdit;
        addButton.Enabled = !working && snapshot is not null && (retryAdd is not null || (manual ? manualDescriptionBox.Text.Trim().Length > 0 : priceList.SelectedIndex >= 0));
        addButton.Text = retryAdd is null ? "Add item" : "Retry item";
    }

    private void FormClosingGuard(object sender, FormClosingEventArgs e) =>
        e.Cancel = working && DialogResult != DialogResult.OK;
}
