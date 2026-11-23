using Npgsql;

namespace Business_Suite;

public sealed partial class PosAnonymousConfigurationForm : Form
{
    private readonly SalesOrderRepository? repository;
    private PosAnonymousConfiguration? account;
    private bool loaded;

    public PosAnonymousConfigurationForm() => InitializeComponent();
    internal PosAnonymousConfigurationForm(SalesOrderRepository repository) : this() => this.repository = repository;

    private async void LoadClicked(object sender, EventArgs e) => await RunAsync(false);
    private async void SaveClicked(object sender, EventArgs e) => await RunAsync(true);

    private async Task RunAsync(bool save)
    {
        if (repository is null || !reloadButton.Enabled)
            return;
        reloadButton.Enabled = saveButton.Enabled = false;
        try
        {
            if (!save)
                account = await repository.LoadPosAnonymousConfigurationAsync();
            else if (account is { } prior)
                account = await repository.SetPosAnonymousStatusAsync(prior.Revision, enabledBox.Checked, reasonBox.Text);
            else if (loaded)
            {
                string existing = existingBox.Text.Trim();
                if (existing.Length == 0)
                    account = await repository.CreatePosAnonymousConfigurationAsync(ledgerBox.Text, countryBox.Text,
                        enabledBox.Checked, reasonBox.Text);
                else if (int.TryParse(existing, out int customer) && customer > 0)
                    account = await repository.SelectPosAnonymousConfigurationAsync(ledgerBox.Text, countryBox.Text,
                        enabledBox.Checked, reasonBox.Text, customer);
                else
                    throw new ArgumentException("Enter the positive ID of the existing dedicated account.");
            }
            if (IsDisposed)
                return;
            loaded = true;
            accountLabel.Text = account is { } current
                ? $"{current.Label} ({current.Country}) · Revision {current.Revision}" : "No counter account configured";
            enabledBox.Checked = account?.Enabled == true;
            ledgerBox.Text = account?.Label ?? "";
            countryBox.Text = account?.Country ?? "";
            existingBox.Text = "";
            saveButton.Text = account is null ? "Save setup" : "Save status";
            reasonBox.Clear();
            statusLabel.Text = save ? "Counter account status saved." :
                account is null ? "Leave the existing account ID blank to create a dedicated ledger." : "A company administrator can change this status.";
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or ArgumentException or
            UnauthorizedAccessException or InvalidOperationException)
        {
            if (!IsDisposed)
                statusLabel.Text = error is NpgsqlException or TimeoutException ? "Could not access account settings. Reload and check the database connection." : error.Message;
        }
        finally
        {
            if (!IsDisposed)
            {
                reloadButton.Enabled = true;
                saveButton.Enabled = enabledBox.Enabled = reasonBox.Enabled = loaded;
                ledgerBox.Enabled = countryBox.Enabled = existingBox.Enabled = loaded && account is null;
            }
        }
    }
}
