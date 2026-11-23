using System.Globalization;
using Npgsql;

namespace Business_Suite;

public sealed partial class PosClosingForm : Form
{
    private readonly SalesOrderRepository? repository;
    private readonly PosCashSnapshot? snapshot;
    private bool saving;

    public PosClosingForm()
    {
        InitializeComponent();
    }

    internal PosClosingForm(SalesOrderRepository repository, PosCashSnapshot snapshot) : this()
    {
        this.repository = repository;
        this.snapshot = snapshot;
        Text = $"Cashier closing | {snapshot.Number}";
        totalsLabel.Text = $"Opening cash  {snapshot.Opening:N2}     Cash sales  {snapshot.Sales:N2}\r\n" +
            $"Cash in  {snapshot.CashIn:N2}     Cash out  {snapshot.CashOut:N2}\r\n" +
            $"Expected cash  {snapshot.Currency} {snapshot.Expected:N2}";
    }

    private void CountChanged(object sender, EventArgs e)
    {
        if (snapshot is null)
            return;
        statusLabel.Text = decimal.TryParse(countBox.Text, NumberStyles.Number, CultureInfo.CurrentCulture, out var count) &&
            count >= 0 && count < 1_000_000_000_000m
            ? $"Variance  {count - snapshot.Expected:N2}" : "";
    }

    private async void PostClosing(object sender, EventArgs e)
    {
        if (repository is null || snapshot is null || saving)
            return;
        if (!decimal.TryParse(countBox.Text, NumberStyles.Number, CultureInfo.CurrentCulture, out decimal counted))
        {
            statusLabel.Text = "Enter counted cash to close the register.";
            return;
        }
        saving = true;
        postButton.Enabled = cancelButton.Enabled = countBox.Enabled = notesBox.Enabled = false;
        statusLabel.Text = "Posting cashier closing…";
        try
        {
            await repository.CloseRegisterAsync(snapshot, counted, notesBox.Text.Trim());
            DialogResult = DialogResult.OK;
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException or
            InvalidOperationException or ArgumentException)
        {
            statusLabel.Text = error is NpgsqlException or TimeoutException
                ? "Could not confirm closing. Refresh the POS sessions before retrying." : error.Message;
        }
        finally
        {
            saving = false;
            if (!IsDisposed)
                postButton.Enabled = cancelButton.Enabled = countBox.Enabled = notesBox.Enabled = true;
        }
    }

    private void ClosingFormClosing(object sender, FormClosingEventArgs e)
    {
        if (saving && DialogResult != DialogResult.OK)
            e.Cancel = true;
    }
}
