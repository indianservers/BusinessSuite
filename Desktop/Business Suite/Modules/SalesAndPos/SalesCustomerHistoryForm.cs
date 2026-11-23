using Npgsql;

namespace Business_Suite;

public sealed partial class SalesCustomerHistoryForm : Form
{
    private readonly SalesOrderRepository? repository;
    private readonly int? order;
    private bool busy;
    private int page = 1;
    private long total;
    private string activeCurrency = "";
    private bool activeTestFilter;
    private int? activeCustomer;

    public SalesCustomerHistoryForm() => InitializeComponent();

    internal SalesCustomerHistoryForm(SalesOrderRepository repository, int order) : this()
    {
        this.repository = repository;
        this.order = order;
    }

    internal SalesCustomerHistoryForm(SalesOrderRepository repository) : this()
    {
        this.repository = repository;
        customerSearchBox.Visible = customerList.Visible = findCustomerButton.Visible = true;
        applyButton.Enabled = false;
    }

    private async void FormShown(object sender, EventArgs e)
    {
        if (order.HasValue)
            await LoadPageAsync(1);
        else
            await LoadCustomersAsync();
    }

    private async void FindCustomers(object sender, EventArgs e) => await LoadCustomersAsync();

    private async Task LoadCustomersAsync()
    {
        if (repository is null || busy || order.HasValue)
            return;
        busy = true;
        historyGrid.DataSource = null;
        activeCustomer = null;
        total = 0;
        page = 1;
        UpdateButtons();
        try
        {
            customerList.DisplayMember = nameof(SalesCustomer.Name);
            var customers = await repository.HistoryCustomersAsync(customerSearchBox.Text);
            customerList.DataSource = customers;
            customerList.SelectedIndex = -1;
            headingLabel.Text = "Purchase history";
            statusLabel.Text = customers.Count == 0 ? "No customers with visible invoices match the search."
                : "Choose a customer and apply filters.";
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or
            UnauthorizedAccessException or InvalidOperationException)
        {
            customerList.DataSource = null;
            statusLabel.Text = error is NpgsqlException or TimeoutException ? "Customers could not load." : error.Message;
        }
        finally
        {
            busy = false;
            UpdateButtons();
        }
    }

    private async void FirstPage(object sender, EventArgs e) => await LoadPageAsync(1);
    private async void PreviousPage(object sender, EventArgs e) => await LoadPageAsync(page - 1, false);
    private async void NextPage(object sender, EventArgs e) => await LoadPageAsync(page + 1, false);
    private void SelectionChanged(object sender, EventArgs e) => UpdateButtons();

    private async Task LoadPageAsync(int requestedPage, bool applyFilters = true)
    {
        if (busy || repository is null)
            return;
        busy = true;
        UpdateButtons();
        try
        {
            string currency = applyFilters ? currencyBox.Text.Trim().ToUpperInvariant() : activeCurrency;
            bool includeTest = applyFilters ? includeTestBox.Checked : activeTestFilter;
            int? customer = applyFilters ? (customerList.SelectedItem?.DataBoundItem as SalesCustomer)?.Id : activeCustomer;
            if (order is null && customer is null)
                return;
            var result = order is int source
                ? await repository.SalesCustomerHistoryAsync(source, currency, includeTest, requestedPage)
                : await repository.HistoryForCustomerAsync(customer!.Value, currency, includeTest, requestedPage);
            activeCustomer = customer;
            activeCurrency = currency;
            activeTestFilter = includeTest;
            page = requestedPage;
            total = result.Total;
            historyGrid.DataSource = result.Rows;
            headingLabel.Text = $"Purchase history | {result.Customer}";
            statusLabel.Text = total == 0 ? "No authorized invoices match these filters." : $"{total:N0} invoices | Page {page:N0}";
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or
            UnauthorizedAccessException or InvalidOperationException or ArgumentException)
        {
            historyGrid.DataSource = null;
            total = 0;
            statusLabel.Text = error is NpgsqlException or TimeoutException ? "Purchase history could not load." : error.Message;
        }
        finally
        {
            busy = false;
            UpdateButtons();
        }
    }

    private async void OpenInvoice(object sender, EventArgs e)
    {
        if (busy || repository is null || historyGrid.CurrentRow?.DataBoundItem is not SalesCustomerHistoryRow selected)
            return;
        busy = true;
        UpdateButtons();
        try
        {
            int? customer = activeCustomer;
            var view = order is int orderId
                ? await repository.LoadSalesCustomerHistoryInvoiceAsync(orderId, selected.Id, activeCurrency, activeTestFilter)
                : await repository.OpenInvoiceForHistoryCustomerAsync(customer!.Value, selected.Id, activeCurrency, activeTestFilter);
            if (view.Milestone is { } milestone && view.OrderId is int milestoneOrder)
            {
                var detail = await repository.LoadSalesMilestoneInvoiceAsync(milestoneOrder, milestone.Engagement,
                    milestone.Plan, milestone.Milestone);
                if (detail.Invoice.Id != selected.Id)
                    throw new InvalidOperationException("The billing source changed. Refresh purchase history.");
                using var milestoneViewer = new SalesInvoiceDetailForm(detail, repository, milestoneOrder, milestone);
                milestoneViewer.ShowDialog(this);
                return;
            }
            LinkedSalesInvoice? source = null;
            if (view.OrderId is int sourceId)
            {
                try { source = await repository.FindOrderInvoiceAsync(sourceId); }
                catch (InvalidOperationException) { }
            }
            if (source?.Id == selected.Id && view.OrderId is int directOrder)
            {
                using var directViewer = new SalesInvoiceDetailForm(view.Details, repository, directOrder);
                directViewer.ShowDialog(this);
                return;
            }
            if (await repository.FindPosReceiptForInvoiceAsync(selected.Id) is not null)
            {
                using var receipt = new PosReceiptHistoryForm(repository, selected.Id);
                receipt.ShowDialog(this);
                return;
            }
            using var viewer = new SalesInvoiceDetailForm(view.Details,
                () => order is int sourceOrder
                    ? repository.LoadSalesCustomerHistoryPdfAsync(sourceOrder, selected.Id, activeCurrency, activeTestFilter)
                    : repository.ExportInvoiceForHistoryCustomerAsync(customer!.Value, selected.Id, activeCurrency, activeTestFilter),
                repository.CanExportLinkedInvoiceAsync);
            viewer.ShowDialog(this);
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException or InvalidOperationException)
        {
            statusLabel.Text = error is NpgsqlException or TimeoutException ? "The invoice could not be opened." : error.Message;
        }
        finally
        {
            busy = false;
            UpdateButtons();
        }
    }

    private void UpdateButtons()
    {
        if (applyButton is null || historyGrid is null)
            return;
        bool selected = customerList.SelectedItem?.DataBoundItem is SalesCustomer;
        currencyBox.Enabled = includeTestBox.Enabled = !busy;
        applyButton.Enabled = !busy && (order.HasValue || selected);
        customerSearchBox.Enabled = customerList.Enabled = findCustomerButton.Enabled = !busy;
        previousButton.Enabled = !busy && page > 1;
        nextButton.Enabled = !busy && page < 10000 && (long)page * SalesOrderRepository.CustomerHistoryPageSize < total;
        invoiceButton.Enabled = !busy && historyGrid.CurrentRow?.DataBoundItem is SalesCustomerHistoryRow;
    }

    private void GuardClosing(object sender, FormClosingEventArgs e) => e.Cancel = busy;
}
