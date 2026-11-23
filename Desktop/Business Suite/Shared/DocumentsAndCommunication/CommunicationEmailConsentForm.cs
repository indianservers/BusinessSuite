using Npgsql;

namespace Business_Suite;

public sealed partial class CommunicationEmailConsentForm : Form
{
    private static readonly string[] Choices = ["opted_in", "opted_out", "unsubscribed"];
    private const int AddressOptOutIndex = 3;
    private readonly CommunicationDraftRepository? repository;
    private readonly DraftRecipientReference? reference;
    private readonly string email = "";
    private EmailConsentHistory? current;
    private bool busy;
    private bool reviewing;

    public CommunicationEmailConsentForm()
    {
        InitializeComponent();
        choiceBox.SelectedIndex = 0;
    }

    internal CommunicationEmailConsentForm(CommunicationDraftRepository repository, DraftRecipientReference reference,
        string email) : this()
    {
        this.repository = repository;
        this.reference = reference;
        this.email = email.Trim();
        addressLabel.Text = this.email;
    }

    private async void RefreshClicked(object? sender, EventArgs e) => await RunAsync(LoadAsync);

    private async Task LoadAsync()
    {
        reviewing = false;
        current = null;
        grid.DataSource = null;
        statusLabel.Text = "Loading email consent…";
        current = await repository!.ReadEmailConsentAsync(reference!, email);
        grid.DataSource = current.Rows.Select(row => new
        {
            row.Recorded, Choice = row.Choice.Replace('_', ' '), row.Source
        }).ToList();
        statusLabel.Text = current.HardBlocked ? "Address-wide email opt-out is active."
            : current.Blocked ? "Email opt-out is recorded for this address."
            : "No email opt-out is recorded for this address.";
        feedback.Text = current.Rows.Count == 0 ? "No consent choices are linked to this CRM record." : "";
    }

    private async void ConfirmClicked(object? sender, EventArgs e)
    {
        if (current?.CanRecord != true || !confirmButton.Enabled)
            return;
        int selected = choiceBox.SelectedIndex;
        bool hard = selected == AddressOptOutIndex;
        string evidence = evidenceBox.Text.Trim();
        if (!reviewing)
        {
            reviewing = true;
            feedback.Text = hard
                ? $"Block email to {email} across this company. A later opt-in will not remove this block. Evidence: {evidence}"
                : $"Review {choiceBox.Text.ToLowerInvariant()} for {email}. Evidence: {evidence}";
            UpdateControls();
            return;
        }
        string revision = current.Revision;
        await RunAsync(async () =>
        {
            if (hard)
                await repository!.RecordAddressOptOutAsync(reference!, email, revision, evidence);
            else
                await repository!.RecordEmailConsentAsync(reference!, email, revision, Choices[selected], evidence);
            evidenceBox.Clear();
            await LoadAsync();
            feedback.Text = hard ? "Recorded the address-wide email opt-out." : "Recorded the customer’s email choice.";
        });
    }

    private void InputChanged(object? sender, EventArgs e)
    {
        reviewing = false;
        feedback.Text = "";
        UpdateControls();
    }

    private async Task RunAsync(Func<Task> action)
    {
        if (busy || repository is null || reference is null)
            return;
        busy = true;
        UpdateControls();
        try { await action(); }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or ArgumentException or
            UnauthorizedAccessException or InvalidOperationException)
        {
            feedback.Text = error is NpgsqlException or TimeoutException
                ? "Could not verify the consent action. Refresh before trying again." : error.Message;
            reviewing = false;
        }
        finally
        {
            busy = false;
            UpdateControls();
        }
    }

    private void UpdateControls()
    {
        bool editable = !busy && current?.CanRecord == true;
        refreshButton.Enabled = closeButton.Enabled = !busy;
        choiceBox.Enabled = evidenceBox.Enabled = editable;
        confirmButton.Enabled = editable && choiceBox.SelectedIndex >= 0 && !string.IsNullOrWhiteSpace(evidenceBox.Text);
        if (current?.HardBlocked == true && choiceBox.SelectedIndex == AddressOptOutIndex)
            confirmButton.Enabled = false;
        confirmButton.Text = reviewing ? "Confirm and save" : "Review customer choice";
    }

    private void ConsentClosing(object? sender, FormClosingEventArgs e) => e.Cancel = busy;
}
