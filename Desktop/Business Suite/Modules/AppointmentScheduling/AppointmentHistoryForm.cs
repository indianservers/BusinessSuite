namespace Business_Suite;

public sealed partial class AppointmentHistoryForm : Form
{
    private readonly AppointmentRepository? repository;
    private readonly int appointmentId;
    private readonly CancellationTokenSource lifetime = new();

    public AppointmentHistoryForm() => InitializeComponent();

    internal AppointmentHistoryForm(AppointmentRepository repository, int appointmentId) : this()
    {
        this.repository = repository;
        this.appointmentId = appointmentId;
    }

    private async void LoadClicked(object? sender, EventArgs e)
    {
        if (repository is null || !refreshButton.Enabled)
            return;
        CancellationToken cancellation = lifetime.Token;
        refreshButton.Enabled = false;
        statusLabel.Text = "Loading appointment history…";
        try
        {
            var history = await repository.HistoryAsync(appointmentId, cancellation);
            if (cancellation.IsCancellationRequested)
                return;
            heading.Text = history.Title;
            historyGrid.DataSource = history.Events;
            statusLabel.Text = history.Events.Count == 0 ? "No history was recorded for this appointment."
                : $"Showing {history.Events.Count:N0} latest entries. Times use this workstation's time zone.";
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch (Exception error) when (AppointmentsForm.IsExpected(error))
        {
            if (!cancellation.IsCancellationRequested)
            {
                historyGrid.DataSource = null;
                statusLabel.Text = AppointmentsForm.Friendly(error);
            }
        }
        finally
        {
            if (!cancellation.IsCancellationRequested)
                refreshButton.Enabled = true;
        }
    }

    private void HistoryClosed(object? sender, FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }

    private void HistorySelectionChanged(object? sender, EventArgs e) =>
        reasonBox.Text = (historyGrid.CurrentRow?.DataBoundItem as AppointmentHistoryRow)?.Reason ?? "";
}
