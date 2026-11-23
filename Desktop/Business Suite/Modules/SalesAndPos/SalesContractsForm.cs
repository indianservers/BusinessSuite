using Npgsql;

namespace Business_Suite;

public sealed partial class SalesContractsForm : Form
{
    private readonly SalesOrderRepository? repository;
    private readonly int order;
    private bool busy;
    private bool canCreate;

    public SalesContractsForm() => InitializeComponent();
    internal SalesContractsForm(SalesOrderRepository repository, int order, string number) : this()
    {
        this.repository = repository;
        this.order = order;
        headingLabel.Text = $"Contracts for {number}";
    }

    private async void RefreshClicked(object sender, EventArgs e) => await LoadAsync(null);
    private async void ActivateClicked(object sender, EventArgs e) => await LoadAsync("active");
    private async void ExpireClicked(object sender, EventArgs e) => await LoadAsync("expired");
    private async void RenewClicked(object sender, EventArgs e) => await LoadAsync("renewed");
    private async void TerminateClicked(object sender, EventArgs e) => await LoadAsync("terminated");
    private void SelectionChanged(object sender, EventArgs e) => UpdateButtons();
    private void GuardClosing(object sender, FormClosingEventArgs e) => e.Cancel = busy;
    private async void EditClicked(object sender, EventArgs e)
    {
        if (repository is null || busy || contractsGrid.CurrentRow?.DataBoundItem is not SalesContractRow selected)
            return;
        using var editor = new SalesContractEditForm(repository, order, selected);
        if (editor.ShowDialog(this) == DialogResult.OK)
            await LoadAsync(null);
    }
    private async void NewClicked(object sender, EventArgs e)
    {
        if (repository is null || busy || !canCreate)
            return;
        busy = true;
        UpdateButtons();
        bool created = false;
        try
        {
            var source = await repository.LoadSalesOrderOverviewAsync(order);
            if (IsDisposed)
                return;
            using var editor = new SalesContractEditForm(repository, order, source);
            created = editor.ShowDialog(this) == DialogResult.OK;
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or InvalidOperationException or UnauthorizedAccessException)
        {
            if (!IsDisposed)
                statusLabel.Text = error is NpgsqlException or TimeoutException ? "Could not reopen the source order." : error.Message;
        }
        finally
        {
            busy = false;
            if (!IsDisposed)
                UpdateButtons();
        }
        if (created && !IsDisposed)
            await LoadAsync(null);
    }

    private async Task LoadAsync(string? target)
    {
        if (repository is null || busy)
            return;
        var selected = contractsGrid.CurrentRow?.DataBoundItem as SalesContractRow;
        busy = true;
        UpdateButtons();
        try
        {
            if (target is not null && selected is not null)
                await repository.ChangeSalesContractAsync(order, selected.Id, selected.Status, target);
            var rows = await repository.SalesContractsAsync(order);
            canCreate = await repository.CanCreateSalesContractAsync(order);
            if (IsDisposed)
                return;
            contractsGrid.DataSource = rows;
            if (selected is not null && contractsGrid.Rows.FirstOrDefault(row =>
                row.DataBoundItem is SalesContractRow contract && contract.Id == selected.Id) is { } match)
                contractsGrid.CurrentRow = match;
            statusLabel.Text = rows.Count == 0 ? "No scoped contracts for this order."
                : target is not null ? $"Contract status saved as {target}." : "";
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException
            or ArgumentException or InvalidOperationException)
        {
            if (!IsDisposed)
                statusLabel.Text = error is NpgsqlException or TimeoutException ? "Could not confirm the contract action. Refresh to check."
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
        if (refreshButton is null || termsBox is null)
            return;
        var selected = contractsGrid.CurrentRow?.DataBoundItem as SalesContractRow;
        string status = selected?.Status ?? "";
        termsBox.Text = selected?.Terms ?? "";
        contractsGrid.Enabled = refreshButton.Enabled = !busy;
        activateButton.Enabled = !busy && SalesOrderRepository.IsContractTransition(status, "active");
        expireButton.Enabled = !busy && SalesOrderRepository.IsContractTransition(status, "expired");
        renewButton.Enabled = !busy && SalesOrderRepository.IsContractTransition(status, "renewed");
        terminateButton.Enabled = !busy && SalesOrderRepository.IsContractTransition(status, "terminated");
        editButton.Enabled = !busy && selected is not null;
        newButton.Enabled = !busy && canCreate;
    }
}
