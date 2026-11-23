using Npgsql;

namespace Business_Suite;

public sealed partial class SalesOrderItemsForm : Form
{
    private readonly SalesOrderRepository? repository;
    private readonly int order;
    private bool loading;

    public SalesOrderItemsForm() => InitializeComponent();
    internal SalesOrderItemsForm(SalesOrderRepository repository, int order, string number) : this()
    {
        this.repository = repository;
        this.order = order;
        orderLabel.Text = number;
    }

    internal bool Changed { get; private set; }

    private async void ReloadClicked(object sender, EventArgs e) => await ReviewAsync(null);
    private async void AddClicked(object sender, EventArgs e)
    {
        if (repository is null || loading)
            return;
        using var editor = new SalesOrderAddItemForm(repository, order);
        if (editor.ShowDialog(this) != DialogResult.OK)
            return;
        Changed = true;
        await ReviewAsync(null);
        if (!IsDisposed)
            statusLabel.Text = "Item added and order totals updated.";
    }
    private async void RemoveClicked(object sender, EventArgs e)
    {
        if (confirmBox.Checked && itemsGrid.CurrentRow?.DataBoundItem is RemovableSalesLine item)
            await ReviewAsync(item);
    }
    private void ConfirmChanged(object sender, EventArgs e) => UpdateButtons();
    private void SelectionChanged(object sender, EventArgs e)
    {
        confirmBox.Checked = false;
        UpdateButtons();
    }
    private void ItemsClosing(object sender, FormClosingEventArgs e) => e.Cancel = loading;

    private async Task ReviewAsync(RemovableSalesLine? item)
    {
        if (repository is null || loading)
            return;
        loading = true;
        UpdateButtons();
        try
        {
            if (item is not null)
            {
                await repository.RemoveSalesOrderLineAsync(order, item.Id, item.Revision);
                Changed = true;
            }
            var rows = await repository.RemovableSalesLinesAsync(order);
            if (IsDisposed)
                return;
            itemsGrid.DataSource = rows;
            statusLabel.Text = item is not null ? "Item removed and order totals updated."
                : rows.Count == 0 ? "No removable items for this order." : "Select the saved item to remove.";
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException or
            ArgumentException or InvalidOperationException)
        {
            if (!IsDisposed)
            {
                itemsGrid.DataSource = null;
                statusLabel.Text = error is NpgsqlException or TimeoutException ? "Could not confirm the action. Reload to review saved items." : error.Message;
            }
        }
        finally
        {
            loading = false;
            if (!IsDisposed)
            {
                confirmBox.Checked = false;
                UpdateButtons();
            }
        }
    }

    private void UpdateButtons()
    {
        bool selected = itemsGrid.CurrentRow?.DataBoundItem is RemovableSalesLine;
        itemsGrid.Enabled = reloadButton.Enabled = !loading;
        addButton.Enabled = !loading;
        confirmBox.Enabled = !loading && selected;
        removeButton.Enabled = confirmBox.Enabled && confirmBox.Checked;
    }
}
