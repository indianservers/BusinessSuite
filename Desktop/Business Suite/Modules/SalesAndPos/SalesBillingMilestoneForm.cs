using Npgsql;

namespace Business_Suite;

public sealed partial class SalesBillingMilestoneForm : Form
{
    private readonly SalesOrderRepository? repository;
    private readonly int order;
    private readonly int engagement;
    private readonly int plan;
    private readonly SalesBillingMilestoneRow? original;
    private readonly bool creating;
    private readonly Guid request = Guid.NewGuid();
    private bool busy;

    public SalesBillingMilestoneForm() => InitializeComponent();
    internal SalesBillingMilestoneForm(SalesOrderRepository repository, int order, int engagement, int plan) : this()
    {
        this.repository = repository;
        this.order = order;
        this.engagement = engagement;
        this.plan = plan;
        creating = true;
        Text = "Add billing milestone";
        headingLabel.Visible = reasonLabel.Visible = reasonBox.Visible = approveButton.Visible = invoiceButton.Visible = false;
        nameLabel.Visible = nameBox.Visible = true;
        saveButton.Text = "Add milestone";
        UpdateButtons();
    }
    internal SalesBillingMilestoneForm(SalesOrderRepository repository, int order, int engagement, int plan,
        SalesBillingMilestoneRow original) : this()
    {
        this.repository = repository;
        this.order = order;
        this.engagement = engagement;
        this.plan = plan;
        this.original = original;
        headingLabel.Text = original.Name;
        amountBox.Value = original.Amount;
        scheduledBox.Checked = original.DueDate.HasValue;
        if (original.DueDate is DateTime due)
            duePicker.Value = due;
        statusLabel.Text = original.Invoiced ? "This milestone is already invoiced." : "";
        UpdateButtons();
    }

    private async void SaveClicked(object sender, EventArgs e) => await SaveAsync(false);
    private async void ApproveClicked(object sender, EventArgs e) => await SaveAsync(true);
    private async void InvoiceClicked(object sender, EventArgs e)
    {
        if (repository is null || original is null || busy)
            return;
        busy = true;
        UpdateButtons();
        bool drafted = false;
        try
        {
            if (!original.Invoiced)
            {
                var invoice = await repository.DraftSalesMilestoneInvoiceAsync(order, engagement, plan, original.Id);
                statusLabel.Text = $"Saved draft {invoice.Number}.";
                drafted = true;
            }
            var details = await repository.LoadSalesMilestoneInvoiceAsync(order, engagement, plan, original.Id);
            using var viewer = new SalesInvoiceDetailForm(details, repository, order,
                new SalesMilestoneInvoiceLink(engagement, plan, original.Id));
            viewer.ShowDialog(this);
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException or
            InvalidOperationException or ArgumentException)
        {
            if (!IsDisposed)
                statusLabel.Text = error is NpgsqlException or TimeoutException ? "Could not confirm the invoice. Reload the plan before retrying."
                    : error.Message;
        }
        finally
        {
            busy = false;
            if (!IsDisposed)
            {
                UpdateButtons();
                if (drafted)
                    DialogResult = DialogResult.OK;
            }
        }
    }
    private void ScheduledChanged(object sender, EventArgs e) => UpdateButtons();
    private void GuardClosing(object sender, FormClosingEventArgs e) => e.Cancel = busy && DialogResult != DialogResult.OK;

    private async Task SaveAsync(bool approve)
    {
        if (repository is null || (!creating && original is not { Invoiced: false }) || busy)
            return;
        busy = true;
        UpdateButtons();
        try
        {
            if (creating)
                await repository.CreateSalesBillingMilestoneAsync(order, engagement, plan, nameBox.Text,
                    amountBox.Value, scheduledBox.Checked ? duePicker.Value.Date : null, request);
            else if (approve && original is not null)
                await repository.ApproveSalesBillingMilestoneAsync(order, engagement, plan, original);
            else if (original is not null)
                await repository.AmendSalesBillingMilestoneAsync(order, engagement, plan, original, amountBox.Value,
                    scheduledBox.Checked ? duePicker.Value.Date : null, reasonBox.Text);
            DialogResult = DialogResult.OK;
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException or
            ArgumentException or InvalidOperationException)
        {
            if (!IsDisposed)
                statusLabel.Text = error is NpgsqlException or TimeoutException ? "Could not confirm the change. Reload the billing plan."
                    : error.Message;
        }
        finally
        {
            busy = false;
            if (!IsDisposed)
                UpdateButtons();
        }
    }

    private void UpdateButtons()
    {
        if (saveButton is null || duePicker is null)
            return;
        bool canEdit = !busy && (creating || original is { Invoiced: false });
        amountBox.Enabled = reasonBox.Enabled = scheduledBox.Enabled = saveButton.Enabled = canEdit;
        nameBox.Enabled = canEdit && creating;
        duePicker.Enabled = canEdit && scheduledBox.Checked;
        approveButton.Enabled = canEdit && !creating && original?.Status != "approved";
        invoiceButton.Text = original?.Invoiced == true ? "Open linked invoice" : "Generate invoice draft";
        invoiceButton.Enabled = !busy && original is { Invoiced: true } or { Status: "approved" or "ready" or "completed" };
    }
}
