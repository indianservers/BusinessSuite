using Npgsql;
using System.Globalization;

namespace Business_Suite;

public sealed partial class PosSessionsForm : Form
{
    private readonly SalesOrderRepository? repository;
    private string? activeNumber;
    private readonly PosCashMovementJournal? cashJournal;

    public PosSessionsForm()
    {
        InitializeComponent();
    }

    internal PosSessionsForm(SalesOrderRepository repository) : this()
    {
        this.repository = repository;
        cashJournal = repository.CashMovementJournal();
    }

    private async void RefreshSessions(object sender, EventArgs e)
    {
        await RefreshAsync();
    }

    private async Task RefreshAsync()
    {
        if (repository is null || !refreshButton.Enabled)
            return;
        refreshButton.Enabled = false;
        openRegisterButton.Enabled = false;
        closeRegisterButton.Enabled = false;
        cartButton.Enabled = false;
        drawerButton.Enabled = cashJournal?.HasPending == true;
        openingBox.Enabled = false;
        sessionsGrid.DataSource = null;
        statusLabel.Text = "Loading POS sessions…";
        try
        {
            var sessions = await repository.PosSessionsAsync();
            if (IsDisposed)
                return;
            sessionsGrid.DataSource = sessions;
            statusLabel.Text = sessions.Count == 0 ? "No POS sessions found."
                : "Expected cash, counted cash and variance are shown for closed sessions.";
            var register = await repository.ActiveRegisterAsync();
            if (IsDisposed)
                return;
            activeRegisterLabel.Text = register.Active is { } active
                ? $"Active register {active.Number}   ·   Opening cash {active.Currency} {active.OpeningCash:N2}"
                : "No active register";
            bool pending = cashJournal?.HasPending == true;
            openRegisterButton.Enabled = openingBox.Enabled = register.CanOpen && !pending;
            activeNumber = register.Active?.Number;
            cartButton.Enabled = activeNumber is not null;
            closeRegisterButton.Enabled = register.CanClose && !pending;
            drawerButton.Enabled = register.CanClose || pending;
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException or InvalidOperationException)
        {
            if (!IsDisposed)
            {
                activeRegisterLabel.Text = "Active register unavailable";
                statusLabel.Text = error is UnauthorizedAccessException or InvalidOperationException ? error.Message
                    : "Could not load POS sessions. Check database connectivity and access, then refresh.";
            }
        }
        finally
        {
            if (!IsDisposed)
                refreshButton.Enabled = true;
        }
    }

    private void CounterAccountClicked(object sender, EventArgs e)
    {
        if (repository is null)
            return;
        using var account = new PosAnonymousConfigurationForm(repository);
        account.ShowDialog(this);
    }

    private void ReturnsClicked(object sender, EventArgs e)
    {
        if (repository is null)
            return;
        using var returns = new PosReturnsForm(repository);
        returns.ShowDialog(this);
    }

    private void ReceiptsClicked(object sender, EventArgs e)
    {
        if (repository is null)
            return;
        using var receipts = new PosReceiptHistoryForm(repository);
        receipts.ShowDialog(this);
    }

    private void CollectionsClicked(object sender, EventArgs e)
    {
        if (repository is null)
            return;
        using var collections = new PosGroupedCollectionsForm(repository);
        collections.ShowDialog(this);
    }

    private void CartClicked(object sender, EventArgs e)
    {
        if (repository is null || !cartButton.Enabled)
            return;
        using var cart = new PosCartForm(repository);
        cart.ShowDialog(this);
    }

    private async void DrawerClicked(object sender, EventArgs e)
    {
        if (repository is null || !drawerButton.Enabled)
            return;
        using (var drawer = new PosCashMovementForm(repository, activeNumber))
            drawer.ShowDialog(this);
        if (!IsDisposed)
            await RefreshAsync();
    }

    private void SessionHistoryClicked(object sender, Telerik.WinControls.UI.GridViewCellEventArgs e)
    {
        if (repository is null || e.Row?.DataBoundItem is not PosSessionRow row)
            return;
        using var drawer = new PosCashMovementForm(repository, row.Number, historyOnly: true);
        drawer.ShowDialog(this);
    }

    private async void OpenRegisterClicked(object sender, EventArgs e)
    {
        if (repository is null || !openRegisterButton.Enabled)
            return;
        if (!decimal.TryParse(openingBox.Text, NumberStyles.Number, CultureInfo.CurrentCulture, out decimal cash))
        {
            statusLabel.Text = "Enter a valid opening cash amount.";
            openingBox.Focus();
            return;
        }

        openRegisterButton.Enabled = openingBox.Enabled = refreshButton.Enabled = false;
        statusLabel.Text = "Opening register…";
        try
        {
            await repository.OpenRegisterAsync(cash);
            if (!IsDisposed)
            {
                refreshButton.Enabled = true;
                await RefreshAsync();
            }
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException or
            InvalidOperationException or ArgumentException)
        {
            if (IsDisposed)
                return;
            refreshButton.Enabled = true;
            if (error is ArgumentException)
                openRegisterButton.Enabled = openingBox.Enabled = true;
            statusLabel.Text = error is NpgsqlException or TimeoutException
                ? "Could not confirm the register opening. Refresh to check for an active register."
                : error.Message;
        }
    }

    private async void CloseRegisterClicked(object sender, EventArgs e)
    {
        if (repository is null || activeNumber is null || !closeRegisterButton.Enabled)
            return;
        closeRegisterButton.Enabled = refreshButton.Enabled = false;
        bool refresh = false;
        try
        {
            var snapshot = await repository.ReadRegisterCashAsync(activeNumber);
            if (IsDisposed)
                return;
            using var closing = new PosClosingForm(repository, snapshot);
            refresh = closing.ShowDialog(this) == DialogResult.OK;
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException or InvalidOperationException)
        {
            if (!IsDisposed)
                statusLabel.Text = error is UnauthorizedAccessException or InvalidOperationException ? error.Message
                    : "Could not load register cash. Check database connectivity and access.";
        }
        finally
        {
            if (!IsDisposed)
                closeRegisterButton.Enabled = refreshButton.Enabled = true;
        }
        if (refresh && !IsDisposed)
            await RefreshAsync();
    }
}
