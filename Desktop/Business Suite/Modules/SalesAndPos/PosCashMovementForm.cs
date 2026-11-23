using System.Globalization;
using Npgsql;

namespace Business_Suite;

public sealed partial class PosCashMovementForm : Form
{
    private readonly SalesOrderRepository? repository;
    private readonly PosCashMovementJournal? journal;
    private readonly string? activeNumber;
    private bool busy;

    public PosCashMovementForm()
    {
        InitializeComponent();
    }

    internal PosCashMovementForm(SalesOrderRepository repository, string? activeNumber, bool historyOnly = false) : this()
    {
        this.repository = repository;
        this.activeNumber = activeNumber;
        if (!historyOnly)
            journal = repository.CashMovementJournal();
    }

    private async void LoadDrawer(object sender, EventArgs e)
    {
        if (repository is null)
            return;
        Toggle(false);
        try
        {
            if (journal is null)
            {
                await RefreshRowsAsync(activeNumber);
                return;
            }
            using var lease = journal.Acquire();
            var pending = journal.Read();
            if (pending is not null)
            {
                amountBox.Text = pending.Amount.ToString("F2", CultureInfo.CurrentCulture);
                reasonBox.Text = pending.Reason;
                cashIn.Checked = pending.Type == "cash_in";
                cashOut.Checked = !cashIn.Checked;
                statusLabel.Text = $"Recover the pending cash movement for {pending.Number}.";
            }
            await RefreshRowsAsync(pending?.Number ?? activeNumber);
        }
        catch (Exception error) when (error is NpgsqlException or IOException or TimeoutException or
            UnauthorizedAccessException or InvalidOperationException)
        {
            statusLabel.Text = Message(error);
        }
        finally
        {
            Toggle(true);
        }
    }

    private async void PostMovement(object sender, EventArgs e)
    {
        if (repository is null || journal is null || busy)
            return;
        Toggle(false);
        try
        {
            using var lease = journal.Acquire();
            var intent = journal.Read();
            bool recovering = intent is not null;
            if (intent is null)
            {
                if (activeNumber is null ||
                    !decimal.TryParse(amountBox.Text, NumberStyles.Number, CultureInfo.CurrentCulture, out decimal amount))
                    throw new ArgumentException("Open a register and enter a valid cash amount.");
                intent = new PosCashMovementIntent(activeNumber, Guid.NewGuid(),
                    cashIn.Checked ? "cash_in" : "cash_out", amount, reasonBox.Text.Trim());
                SalesOrderRepository.ValidateCashIntent(intent);
                var snapshot = await repository.ReadRegisterCashAsync(activeNumber);
                if (snapshot.Currency.Length != 3)
                    throw new InvalidOperationException("This register requires a verified cash currency.");
                journal.Save(intent);
            }

            var saved = await repository.PostCashMovementAsync(intent);
            journal.Clear();
            amountBox.Text = "";
            reasonBox.Text = "";
            statusLabel.Text = saved.Id is null
                ? "The previous request was absent when the register closed."
                : recovering ? $"Cash movement #{saved.Id} confirmed." : $"Cash movement #{saved.Id} posted.";
            try
            {
                await RefreshRowsAsync(intent.Number);
            }
            catch (Exception error) when (error is NpgsqlException or TimeoutException)
            {
                statusLabel.Text += " Reopen the drawer history to refresh the list.";
            }
        }
        catch (Exception error) when (error is NpgsqlException or IOException or TimeoutException or
            UnauthorizedAccessException or InvalidOperationException or ArgumentException)
        {
            statusLabel.Text = Message(error);
        }
        finally
        {
            Toggle(true);
        }
    }

    private async Task RefreshRowsAsync(string? number)
    {
        if (repository is null || number is null)
            return;
        registerLabel.Text = $"Cash drawer | {number}";
        var rows = await repository.CashMovementsAsync(number);
        if (!IsDisposed)
            historyGrid.DataSource = rows;
    }

    private void Toggle(bool ready)
    {
        busy = !ready;
        if (IsDisposed)
            return;
        bool pending = journal?.HasPending == true;
        cashIn.Enabled = cashOut.Enabled = amountBox.Enabled = reasonBox.Enabled =
            ready && journal is not null && !pending && activeNumber is not null;
        postButton.Enabled = ready && journal is not null && (pending || activeNumber is not null);
        postButton.Text = pending ? "Recover movement" : "Post movement";
        doneButton.Enabled = ready;
    }

    private void DrawerClosing(object sender, FormClosingEventArgs e)
    {
        if (busy)
            e.Cancel = true;
    }

    private static string Message(Exception error) => error switch
    {
        IOException => "Drawer recovery storage is unavailable or in use by another window.",
        NpgsqlException or TimeoutException => "Could not confirm the cash action. Check PostgreSQL connectivity, then recover the saved request.",
        _ => error.Message
    };
}
