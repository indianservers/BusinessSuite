using Npgsql;

namespace Business_Suite;

public sealed partial class SalesAndPosForm : Form
{
    private readonly SalesOrderRepository? orders;
    private bool loading;
    private bool editing;
    private bool approving;
    private bool draftingInvoice;
    private int? orderWithInvoice;
    private int detailSequence;

    public SalesAndPosForm()
    {
        InitializeComponent();
    }

    internal SalesAndPosForm(DesktopDatabaseSettings settings) : this()
    {
        orders = new SalesOrderRepository(settings);
    }

    private async void WorkspaceShown(object sender, EventArgs e)
    {
        statusFilter.DataSource = new[] { "All statuses", "draft", "pending_approval", "approved",
            "confirmed", "completed", "cancelled", "closed", "archived" };
        await LoadOrdersAsync();
    }

    private async void SearchClicked(object sender, EventArgs e) => await LoadOrdersAsync();
    private void DateFilterChanged(object sender, EventArgs e)
    {
        fromPicker.Enabled = fromCheck.Checked;
        untilPicker.Enabled = untilCheck.Checked;
    }

    private async void NewOrderClicked(object sender, EventArgs e)
    {
        if (orders is null || loading)
            return;
        using var editor = new SalesOrderCreateForm(orders);
        if (editor.ShowDialog(this) == DialogResult.OK && editor.SavedOrder is { } created)
        {
            searchBox.Text = created.Number;
            statusFilter.SelectedIndex = 0;
            fromCheck.Checked = untilCheck.Checked = false;
            await LoadOrdersAsync();
        }
    }

    private void SessionsClicked(object sender, EventArgs e)
    {
        if (orders is null)
            return;
        using var sessions = new PosSessionsForm(orders);
        sessions.ShowDialog(this);
    }

    private async void OverviewClicked(object sender, EventArgs e)
    {
        if (orders is null || loading || ordersGrid.CurrentRow?.DataBoundItem is not SalesOrderRow selected)
            return;
        using var detail = new SalesOrderOverviewForm(orders, selected.Id);
        detail.ShowDialog(this);
        if (detail.Changed && !IsDisposed)
        {
            searchBox.Text = detail.RevisedOrder?.Number ?? selected.OrderNumber;
            statusFilter.SelectedIndex = detail.Archived ? statusFilter.Items.Count - 1 : 0;
            if (detail.RevisedOrder is not null)
                fromCheck.Checked = untilCheck.Checked = false;
            await LoadOrdersAsync();
        }
    }

    private async void ApprovalClicked(object sender, EventArgs e)
    {
        if (orders is null || approving || loading || !approvalButton.Enabled ||
            ordersGrid.CurrentRow?.DataBoundItem is not SalesOrderRow { Status: "draft" or "pending_approval" or "approved" } selected)
            return;
        approving = true;
        approvalButton.Enabled = false;
        statusLabel.Text = "Saving sales order…";
        try
        {
            string message;
            if (selected.Status == "approved")
            {
                var confirmed = await orders.ConfirmSalesOrderAsync(selected.Id);
                message = $"Confirmed {selected.OrderNumber}. Engagement #{confirmed.EngagementId} · Billing plan #{confirmed.BillingPlanId}.";
            }
            else
            {
                var result = await orders.AdvanceSalesApprovalAsync(selected.Id, selected.Status == "pending_approval");
                message = result.Status == "pending_approval"
                    ? $"Sent to Finance for approval · Request #{result.ApprovalRequestId}."
                    : $"Sales order {selected.OrderNumber} approved.";
            }
            if (IsDisposed)
                return;
            searchBox.Text = selected.OrderNumber;
            statusFilter.SelectedIndex = 0;
            await LoadOrdersAsync();
            if (!IsDisposed)
                statusLabel.Text = message;
        }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException or NpgsqlException or TimeoutException)
        {
            if (!IsDisposed)
                statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException ? error.Message
                    : "Could not save the sales order action. Refresh the order before retrying.";
        }
        finally
        {
            approving = false;
            if (!IsDisposed)
                await UpdateApprovalButtonAsync(detailSequence);
        }
    }

    private void SalesPipelineClicked(object sender, EventArgs e)
    {
        if (orders is null)
            return;
        using var pipeline = new SalesPipelineForm(orders);
        pipeline.ShowDialog(this);
    }

    private void CustomerHistoryClicked(object sender, EventArgs e)
    {
        if (orders is null)
            return;
        using var history = new SalesCustomerHistoryForm(orders);
        history.ShowDialog(this);
    }

    private async void InvoiceClicked(object sender, EventArgs e)
    {
        if (orders is null || draftingInvoice || loading || !invoiceButton.Enabled ||
            ordersGrid.CurrentRow?.DataBoundItem is not SalesOrderRow selected)
            return;
        draftingInvoice = true;
        invoiceButton.Enabled = false;
        try
        {
            if (orderWithInvoice == selected.Id)
            {
                var detail = await orders.LoadOrderInvoiceAsync(selected.Id);
                if (!IsDisposed)
                {
                    using var invoiceViewer = new SalesInvoiceDetailForm(detail, orders, selected.Id);
                    invoiceViewer.ShowDialog(this);
                }
            }
            else
            {
                statusLabel.Text = $"Creating invoice draft for {selected.OrderNumber}…";
                var invoice = await orders.DraftSalesInvoiceAsync(selected.Id);
                if (!IsDisposed)
                    statusLabel.Text = $"Invoice draft {invoice.Number} · {invoice.Currency} {invoice.Total:N2} · Due {invoice.Due:d}.";
            }
        }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException or NpgsqlException or TimeoutException)
        {
            if (!IsDisposed)
                statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException ? error.Message
                    : "Could not complete the invoice action. Refresh the order before retrying.";
        }
        finally
        {
            draftingInvoice = false;
            if (!IsDisposed)
                await UpdateInvoiceButtonAsync(detailSequence);
        }
    }

    private async Task UpdateInvoiceButtonAsync(int sequence)
    {
        if (orders is null || draftingInvoice || IsDisposed ||
            ordersGrid.CurrentRow?.DataBoundItem is not SalesOrderRow selected)
            return;
        try
        {
            var linked = await orders.FindOrderInvoiceAsync(selected.Id);
            bool permitted = linked is not null || await orders.CanDraftSalesInvoiceAsync(selected.Id);
            if (!IsDisposed && sequence == detailSequence)
            {
                orderWithInvoice = linked is not null ? selected.Id : null;
                invoiceButton.Text = linked is not null ? "Open linked invoice" : "Create invoice draft";
                invoiceButton.Enabled = permitted && !draftingInvoice;
            }
        }
        catch (Exception error) when (error is InvalidOperationException or NpgsqlException or TimeoutException)
        {
            if (!IsDisposed && sequence == detailSequence)
                invoiceButton.Enabled = false;
        }
    }

    private async void EditOrderClicked(object sender, EventArgs e)
    {
        if (orders is null || ordersGrid.CurrentRow?.DataBoundItem is not SalesOrderRow selected)
            return;
        editing = true;
        editOrderButton.Enabled = false;
        try
        {
            var draft = await orders.LoadEditAsync(selected.Id);
            if (IsDisposed)
                return;
            using var editor = new SalesOrderEditForm(orders, draft);
            if (editor.ShowDialog(this) == DialogResult.OK)
                await LoadOrdersAsync();
        }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException or NpgsqlException or TimeoutException)
        {
            if (!IsDisposed)
                statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException ? error.Message
                    : "Could not open the draft editor. Check the database connection, then refresh.";
        }
        finally
        {
            editing = false;
            if (!IsDisposed)
                UpdateEditButton();
        }
    }

    private void UpdateEditButton()
    {
        editOrderButton.Enabled = !editing && orders is not null &&
            ordersGrid.CurrentRow?.DataBoundItem is SalesOrderRow { Status: "draft" or "created" or "planned" };
    }

    private async Task LoadOrdersAsync()
    {
        if (loading)
            return;
        if (orders is null)
        {
            statusLabel.Text = "Sales order access requires an authorized Sales session.";
            searchButton.Enabled = false;
            sessionsButton.Enabled = false;
            return;
        }

        loading = true;
        searchButton.Enabled = false;
        newOrderButton.Enabled = false;
        approvalButton.Enabled = false;
        invoiceButton.Enabled = false;
        overviewButton.Enabled = false;
        ordersGrid.DataSource = null;
        linesGrid.DataSource = null;
        ++detailSequence;
        statusLabel.Text = "Loading sales orders…";
        try
        {
            string status = statusFilter.SelectedIndex > 0 ? statusFilter.Text : "";
            var rows = await orders.ListFilteredAsync(searchBox.Text.Trim(), status,
                fromCheck.Checked ? fromPicker.Value.Date : null, untilCheck.Checked ? untilPicker.Value.Date : null);
            if (IsDisposed)
                return;
            ordersGrid.DataSource = rows;
            statusLabel.Text = rows.Count == 0 ? "No sales orders match the filters."
                : rows.Count == SalesOrderRepository.ResultLimit ? "Showing the latest 200 matching orders. Refine the filters to find older orders."
                : rows.Count == 1 ? "1 sales order"
                : $"{rows.Count} sales orders";
            bool canCreate = await orders.CanCreateSalesOrderAsync();
            if (!IsDisposed)
                newOrderButton.Enabled = canCreate;
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException or ArgumentException)
        {
            if (!IsDisposed)
                statusLabel.Text = error is UnauthorizedAccessException or ArgumentException ? error.Message
                    : "Could not load sales orders. Check database connectivity and access, then refresh.";
        }
        finally
        {
            loading = false;
            if (!IsDisposed)
                searchButton.Enabled = true;
        }
    }

    private async void OrderSelectionChanged(object sender, EventArgs e)
    {
        int sequence = ++detailSequence;
        UpdateEditButton();
        approvalButton.Enabled = false;
        invoiceButton.Enabled = false;
        overviewButton.Enabled = ordersGrid.CurrentRow?.DataBoundItem is SalesOrderRow;
        linesGrid.DataSource = null;
        if (orders is null || ordersGrid.CurrentRow?.DataBoundItem is not SalesOrderRow order)
        {
            linesLabel.Text = "Order items";
            return;
        }
        string reference = string.IsNullOrWhiteSpace(order.OrderNumber) ? order.Title : order.OrderNumber;
        linesLabel.Text = $"Loading items for {reference}…";
        try
        {
            var rows = await orders.LinesAsync(order.Id);
            if (IsDisposed || sequence != detailSequence)
                return;
            linesGrid.DataSource = rows;
            linesLabel.Text = rows.Count == 0 ? $"No items shown for {reference}" : $"Items for {reference}";
            await Task.WhenAll(UpdateApprovalButtonAsync(sequence), UpdateInvoiceButtonAsync(sequence));
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException)
        {
            if (!IsDisposed && sequence == detailSequence)
                linesLabel.Text = "Could not load order items.";
        }
    }

    private async Task UpdateApprovalButtonAsync(int sequence)
    {
        if (orders is null || approving || IsDisposed ||
            ordersGrid.CurrentRow?.DataBoundItem is not SalesOrderRow { Status: "draft" or "pending_approval" or "approved" } selected)
            return;
        approvalButton.Text = selected.Status switch
        {
            "approved" => "Confirm sales order",
            "pending_approval" => "Approve sales order",
            _ => "Submit for approval"
        };
        try
        {
            bool permitted = await orders.CanAdvanceApprovalAsync(selected.Id, selected.Status);
            if (!IsDisposed && sequence == detailSequence)
                approvalButton.Enabled = permitted && !approving;
        }
        catch (Exception error) when (error is InvalidOperationException or NpgsqlException or TimeoutException)
        {
            if (!IsDisposed && sequence == detailSequence)
                approvalButton.Enabled = false;
        }
    }
}
