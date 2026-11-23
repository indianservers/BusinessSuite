using Npgsql;

namespace Business_Suite;

public sealed partial class PosCartForm : Form
{
    private readonly SalesOrderRepository? repository;
    private readonly List<PosCartLine> cart = new();
    private PosCartOptions? options;
    private SalesIntentJournal<PosHoldCart>? journal;
    private FileStream? journalLock;
    private PosHoldCart? pending;
    private bool busy;
    private bool canCheckout;
    private bool canCheckoutCredit;
    private bool canCheckoutAnonymous;
    private SalesIntentJournal<PosCheckoutIntent>? checkoutJournal;
    private FileStream? checkoutLock;
    private PosCheckoutIntent? pendingCheckout;

    public PosCartForm() => InitializeComponent();
    internal PosCartForm(SalesOrderRepository repository) : this() => this.repository = repository;

    private async void CartShown(object sender, EventArgs e) => await LoadAsync();
    private async void SearchClicked(object sender, EventArgs e) => await LoadAsync();
    private async void HistoryFilterChanged(object sender, EventArgs e) => await LoadAsync();
    private void CartSelectionChanged(object sender, EventArgs e) => ApplyButtons();

    private async void SearchKeyPressed(object sender, KeyEventArgs e)
    {
        if (e.KeyCode != Keys.Enter || busy)
            return;
        e.SuppressKeyPress = true;
        await LoadAsync();
        if (catalogGrid.DataSource is List<PosCartProduct> rows)
        {
            string key = searchBox.Text.Trim();
            var exact = rows.FirstOrDefault(row => key.Length > 0 && (row.Barcode == key ||
                row.Sku.Equals(key, StringComparison.OrdinalIgnoreCase)));
            if (exact is not null && addButton.Enabled)
                AddProduct(exact);
        }
    }

    private async Task LoadAsync(string? message = null)
    {
        if (repository is null || busy)
            return;
        busy = true;
        ApplyButtons();
        try
        {
            int selectedCustomer = customerPicker.SelectedValue is int id ? id : 0;
            var page = await repository.PosCartOptionsAsync(searchBox.Text);
            var held = await repository.ListHeldPosCartsAsync(showRecalled.Checked);
            if (IsDisposed)
                return;
            if (options is not null && page.Register != options.Register)
                throw new InvalidOperationException("The active register changed. Close and reopen the cart.");
            options = page;
            canCheckout = await repository.CanCheckoutPosCashAsync();
            canCheckoutCredit = await repository.CanCheckoutPosCreditAsync();
            canCheckoutAnonymous = canCheckout && await repository.CanCheckoutAnonymousPosCashAsync();
            if ((canCheckout || canCheckoutCredit) && checkoutJournal is null)
            {
                checkoutJournal = repository.PosCheckoutJournal();
                checkoutLock = checkoutJournal.Acquire();
                pendingCheckout = checkoutJournal.Read();
            }
            if (journal is null && page.CanChange)
            {
                journal = repository.HeldCartJournal(page.Register);
                journalLock = journal.Acquire();
                pending = journal.Read();
            }
            headingLabel.Text = $"{page.Register} · POS cart · {page.Currency}";
            var customers = new List<SalesCustomer> { new(0, "Walk-in") };
            customers.AddRange(page.Customers);
            customerPicker.DataSource = customers;
            customerPicker.DisplayMember = "Name";
            customerPicker.ValueMember = "Id";
            customerPicker.SelectedValue = pending?.CustomerId ?? selectedCustomer;
            if (customerPicker.SelectedIndex < 0)
                customerPicker.SelectedIndex = 0;
            if (pending is not null)
                notesBox.Text = pending.Notes;
            catalogGrid.DataSource = page.Products;
            heldGrid.DataSource = held;
            statusLabel.Text = message ?? (pendingCheckout is not null ? $"Recover checkout for {pendingCheckout.Register} · {pendingCheckout.Currency} {pendingCheckout.Total:N2}."
                : pending is not null ? "A saved hold request must be resolved before editing the cart."
                : held.Count == 0 ? "No held bills." : $"{held.Count} matching bills.");
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException
            or InvalidOperationException or IOException)
        {
            if (!IsDisposed)
                statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException ? error.Message
                    : error is IOException ? "The cart recovery folder is unavailable or another window owns this register cart."
                    : "Could not load the cart. Check PostgreSQL access and refresh.";
        }
        finally
        {
            busy = false;
            if (!IsDisposed)
                ApplyButtons();
        }
    }

    private void AddClicked(object sender, EventArgs e)
    {
        if (catalogGrid.CurrentRow?.DataBoundItem is PosCartProduct product)
            AddProduct(product);
    }

    private void AddProduct(PosCartProduct product)
    {
        if (!addButton.Enabled)
            return;
        try
        {
            var line = SalesOrderRepository.PriceCartLine(product, quantityEditor.Value);
            int index = cart.FindIndex(row => row.ProductId == product.Id);
            if (index >= 0)
                cart[index] = line;
            else if (cart.Count < 100)
                cart.Add(line);
            else
                throw new InvalidOperationException("The cart supports up to 100 products.");
            RefreshCart();
        }
        catch (Exception error) when (error is ArgumentException or InvalidOperationException)
        {
            statusLabel.Text = error.Message;
        }
    }

    private void RemoveClicked(object sender, EventArgs e)
    {
        if (removeButton.Enabled && cartGrid.CurrentRow?.DataBoundItem is PosCartLine line)
        {
            cart.Remove(line);
            RefreshCart();
        }
    }

    private void RefreshCart()
    {
        cartGrid.DataSource = cart.ToList();
        cartLabel.Text = $"Current cart · {options?.Currency} {cart.Sum(line => line.LineTotal):N2}";
        ApplyButtons();
    }

    private async void CheckoutClicked(object sender, EventArgs e)
    {
        if (repository is null || options is null || checkoutJournal is null || checkoutLock is null || !checkoutButton.Enabled)
            return;
        PosCheckoutIntent? request = pendingCheckout;
        if (request is null)
        {
            if (customerPicker.SelectedItem?.DataBoundItem is not SalesCustomer buyer || (buyer.Id == 0 && !canCheckoutAnonymous))
                return;
            decimal total = cart.Sum(l => l.LineTotal);
            using var confirmation = new PosCashCheckoutForm(buyer.Name, options.Currency, total, buyer.Id == 0, canCheckout, canCheckoutCredit);
            if (confirmation.ShowDialog(this) != DialogResult.OK)
                return;
            IReadOnlyList<PosTenderPart>? parts = null;
            if (confirmation.Tender == "split")
            {
                using var split = new PosSplitTenderForm(total, options.Currency, requiresFullPayment: buyer.Id == 0);
                if (split.ShowDialog(this) != DialogResult.OK || split.SavedPayments is null)
                    return;
                parts = split.SavedPayments;
            }
            request = new PosCheckoutIntent(Guid.NewGuid(), Guid.NewGuid(), options.Register, options.Currency, buyer.Id,
                notesBox.Text, total, cart.Select(l => new PosCheckoutItem(Guid.NewGuid(), l.ProductId,
                    l.Quantity, l.UnitPrice, l.TaxRate)).ToList())
            {
                Tender = confirmation.Tender,
                Reference = confirmation.Reference,
                Parts = parts
            };
        }
        busy = true;
        ApplyButtons();
        try
        {
            if (pendingCheckout is null)
            {
                checkoutJournal.Save(request);
                pendingCheckout = request;
            }
            statusLabel.Text = "Posting checkout…";
            var result = await repository.CheckoutPosCashAsync(request);
            checkoutJournal.Clear();
            pendingCheckout = null;
            cart.Clear();
            notesBox.Clear();
            customerPicker.SelectedIndex = 0;
            RefreshCart();
            statusLabel.Text = result.ReceiptNumber is not null
                ? $"Invoice {result.InvoiceNumber} · Paid {result.Currency} {result.Total - result.Outstanding:N2} · Outstanding {result.Outstanding:N2}" +
                    (result.Change > 0 ? $" · Change {result.Change:N2}" : "") + $" · Receipt {result.ReceiptNumber}."
                : $"Credit invoice {result.InvoiceNumber} · Order {result.OrderNumber} · {result.Currency} {result.Outstanding:N2} outstanding.";
        }
        catch (PosCheckoutRejectedException error)
        {
            try
            {
                checkoutJournal.Clear();
                pendingCheckout = null;
                statusLabel.Text = error.Message;
            }
            catch (Exception storage) when (storage is IOException or UnauthorizedAccessException)
            {
                statusLabel.Text = "Checkout was rejected. Local recovery storage could not be cleared.";
            }
        }
        catch (Exception error) when (error is ArgumentException or InvalidOperationException or NpgsqlException
            or UnauthorizedAccessException or IOException or TimeoutException)
        {
            statusLabel.Text = error is ArgumentException or InvalidOperationException or UnauthorizedAccessException ? error.Message
                : pendingCheckout is null ? "Checkout recovery could not be saved. No checkout was posted."
                : "Checkout outcome is uncertain. Retry the same saved request.";
        }
        finally
        {
            busy = false;
            ApplyButtons();
        }
    }

    private async void HoldClicked(object sender, EventArgs e)
    {
        if (repository is null || options is null || journal is null || journalLock is null || !holdButton.Enabled)
            return;
        busy = true;
        ApplyButtons();
        string? message = null;
        try
        {
            if (pending is null)
            {
                var request = new PosHoldCart(Guid.NewGuid(), customerPicker.SelectedValue is int id && id > 0 ? id : null,
                    notesBox.Text, cart.Select(line => new PosCartEntry(line.ProductId, line.Quantity)).ToList());
                journal.Save(request);
                pending = request;
            }
            var saved = await repository.HoldPosCartAsync(options.Register, pending);
            journal.Clear();
            pending = null;
            cart.Clear();
            notesBox.Clear();
            customerPicker.SelectedIndex = 0;
            RefreshCart();
            message = $"{saved.Number} held · {options.Currency} {saved.Lines.Sum(line => line.LineTotal):N2}.";
        }
        catch (PosHoldRejectedException error)
        {
            try
            {
                journal.Clear();
                pending = null;
                statusLabel.Text = error.Message;
            }
            catch (Exception storage) when (storage is IOException or UnauthorizedAccessException)
            {
                statusLabel.Text = "The hold was rejected. Local recovery storage could not be cleared.";
            }
        }
        catch (Exception error) when (error is ArgumentException or NpgsqlException or TimeoutException or UnauthorizedAccessException
            or InvalidOperationException or IOException)
        {
            statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException or ArgumentException ? error.Message
                : pending is null ? "The hold request could not be saved locally." : "Hold outcome is uncertain. Retry the same request.";
        }
        finally
        {
            busy = false;
            ApplyButtons();
        }
        if (message is not null)
            await LoadAsync(message);
    }

    private async void RecallClicked(object sender, EventArgs e) => await ResolveSelectionAsync(false);
    private async void CancelClicked(object sender, EventArgs e) => await ResolveSelectionAsync(true);

    private async Task ResolveSelectionAsync(bool cancel)
    {
        if (repository is null || busy || pending is not null || heldGrid.CurrentRow?.DataBoundItem is not PosHeldBillRow row ||
            (cancel ? !voidButton.Enabled : !recallButton.Enabled))
            return;
        busy = true;
        ApplyButtons();
        string? message = null;
        try
        {
            var held = await repository.ResolveHeldPosCartAsync(row.Id, cancel);
            if (!cancel)
            {
                cart.Clear();
                cart.AddRange(held.Lines);
                notesBox.Text = held.Notes;
                if (held.CustomerId is int customer && customerPicker.DataSource is List<SalesCustomer> customers &&
                    customers.All(c => c.Id != customer))
                {
                    var updated = customers.ToList();
                    updated.Add(new SalesCustomer(customer, held.Customer));
                    customerPicker.DataSource = updated;
                    customerPicker.DisplayMember = "Name";
                    customerPicker.ValueMember = "Id";
                }
                customerPicker.SelectedValue = held.CustomerId ?? 0;
                RefreshCart();
            }
            message = cancel ? $"{held.Number} cancelled." : $"{held.Number} restored to cart.";
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException or InvalidOperationException)
        {
            statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException ? error.Message
                : "Could not confirm the action. Refresh and include recalled bills before retrying.";
        }
        finally
        {
            busy = false;
            ApplyButtons();
        }
        if (message is not null)
            await LoadAsync(message);
    }

    private void ApplyButtons()
    {
        bool writable = !busy && options?.CanChange == true && journalLock is not null;
        bool editing = writable && pending is null && pendingCheckout is null;
        addButton.Enabled = editing && catalogGrid.CurrentRow?.DataBoundItem is PosCartProduct;
        removeButton.Enabled = editing && cartGrid.CurrentRow?.DataBoundItem is PosCartLine;
        holdButton.Text = pending is null ? "Hold bill" : "Retry same hold";
        holdButton.Enabled = writable && pendingCheckout is null && (pending is not null || cart.Count > 0);
        checkoutButton.Text = pendingCheckout is null ? "Checkout" : "Retry same checkout";
        checkoutButton.Enabled = writable && (canCheckout || canCheckoutCredit) && checkoutLock is not null && pending is null &&
            (pendingCheckout is not null || (cart.Count > 0 && cart.Sum(l => l.LineTotal) > 0 &&
                customerPicker.SelectedValue is int customer && (customer > 0 || canCheckoutAnonymous)));
        recallButton.Enabled = editing && cart.Count == 0 && heldGrid.CurrentRow?.DataBoundItem is PosHeldBillRow;
        voidButton.Enabled = !busy && pending is null && pendingCheckout is null && options?.CanCancel == true &&
            heldGrid.CurrentRow?.DataBoundItem is PosHeldBillRow { Status: "held" };
        quantityEditor.Enabled = customerPicker.Enabled = notesBox.Enabled = editing;
        searchButton.Enabled = closeButton.Enabled = showRecalled.Enabled = !busy;
    }

    private void CartClosing(object sender, FormClosingEventArgs e)
    {
        if (busy)
            e.Cancel = true;
        else
        {
            journalLock?.Dispose();
            checkoutLock?.Dispose();
        }
    }
}
