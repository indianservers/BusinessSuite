using Npgsql;

namespace Business_Suite;

public sealed partial class CommunicationCampaignHistoryForm : Form
{
    private readonly CommunicationDraftRepository? repository;
    private readonly int campaign;
    private bool busy;

    public CommunicationCampaignHistoryForm() => InitializeComponent();

    internal CommunicationCampaignHistoryForm(CommunicationDraftRepository repository, EmailCampaign selected) : this()
    {
        this.repository = repository;
        campaign = selected.Id;
        heading.Text = $"Campaign #{campaign} · {selected.Name}";
    }

    private async void RefreshClicked(object? sender, EventArgs e)
    {
        if (repository is null || busy)
            return;
        busy = true;
        refreshButton.Enabled = false;
        deliveriesGrid.DataSource = changesGrid.DataSource = null;
        deliveryStatus.Text = changesStatus.Text = "Loading campaign history…";
        try
        {
            var history = await repository.CampaignHistoryAsync(campaign);
            if (IsDisposed)
                return;
            deliveriesGrid.DataSource = history.Deliveries;
            changesGrid.DataSource = history.Changes;
            deliveryStatus.Text = !history.DeliveryAvailable ? "Delivery history requires access to CRM recipients and communication logs."
                : history.Deliveries.Count == 0 ? "No recorded delivery activity is visible in this branch."
                : $"Showing {history.Deliveries.Count} recorded event(s) visible in this branch.";
            changesStatus.Text = history.Changes.Count == 0 ? "No campaign changes were recorded in this branch."
                : $"Showing {history.Changes.Count} recorded change(s).";
        }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or UnauthorizedAccessException or InvalidOperationException)
        {
            if (!IsDisposed)
                changesStatus.Text = deliveryStatus.Text = error is NpgsqlException or TimeoutException
                    ? "Could not load campaign history. Check database connectivity and access, then refresh." : error.Message;
        }
        finally
        {
            busy = false;
            if (!IsDisposed)
                refreshButton.Enabled = true;
        }
    }
}
