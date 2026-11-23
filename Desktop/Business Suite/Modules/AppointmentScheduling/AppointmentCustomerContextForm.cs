namespace Business_Suite;

public sealed partial class AppointmentCustomerContextForm : Form
{
    private readonly AppointmentRepository? repository;
    private readonly int customer;
    private readonly int? service, provider;
    private readonly DateTime start;
    private readonly HashSet<int>? eligible;
    private readonly CancellationTokenSource lifetime = new();
    private AppointmentOption? preferred;
    private bool loading;
    private readonly bool replaceDraft;
    private int? confirmRepeat;
    private string visitNotice = "";

    public AppointmentCustomerContextForm() => InitializeComponent();

    internal AppointmentCustomerContextForm(AppointmentRepository repository, int customer, int? service,
        int? provider, DateTime start, HashSet<int>? eligible)
        : this(repository, customer, service, provider, start, eligible, false) { }

    internal AppointmentCustomerContextForm(AppointmentRepository repository, int customer, int? service,
        int? provider, DateTime start, HashSet<int>? eligible, bool replaceDraft) : this()
    {
        this.repository = repository;
        this.customer = customer;
        this.service = service;
        this.provider = provider;
        this.start = start;
        this.eligible = eligible;
        this.replaceDraft = replaceDraft;
    }

    internal int? SuggestedProvider { get; private set; }
    internal AppointmentRebookSeed? RepeatDraft { get; private set; }

    private async void LoadClicked(object? sender, EventArgs e)
    {
        if (repository is null || loading)
            return;
        loading = true;
        UpdateActions();
        notice.Text = "Loading permitted customer visits…";
        var cancellation = lifetime.Token;
        try
        {
            var summary = await repository.CustomerContextAsync(customer, service, provider, start, cancellation);
            if (cancellation.IsCancellationRequested)
                return;
            heading.Text = $"{summary.Customer} · Visits";
            preferred = summary.Preferred;
            suggestion.Text = preferred is null ? "No provider suggestion from recent visits."
                : $"Suggested provider: {preferred.Name}";
            grid.DataSource = summary.Visits;
            int duplicates = summary.Visits.Count(item => item.Group == "Possible duplicate");
            visitNotice = duplicates > 0
                ? $"{duplicates} possible duplicate {(duplicates == 1 ? "booking" : "bookings")}. Review before confirming. Times in {summary.Zone}."
                : summary.Visits.Count == 0 ? "No recent or upcoming visits in this branch." : $"Times in {summary.Zone}.";
            notice.Text = visitNotice;
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch (Exception error) when (AppointmentsForm.IsExpected(error))
        {
            if (!cancellation.IsCancellationRequested)
            {
                preferred = null;
                grid.DataSource = null;
                notice.Text = AppointmentsForm.Friendly(error);
            }
        }
        finally
        {
            if (!cancellation.IsCancellationRequested)
            {
                loading = false;
                UpdateActions();
            }
        }
    }

    private void GridSelectionChanged(object? sender, EventArgs e)
    {
        if (confirmRepeat.HasValue)
            notice.Text = visitNotice;
        confirmRepeat = null;
        UpdateActions();
    }

    private void UpdateActions()
    {
        if (inspectButton is null || refreshButton is null || repeatButton is null)
            return;
        inspectButton.Enabled = !loading && grid.CurrentRow?.DataBoundItem is AppointmentVisitContextRow;
        suggestionButton.Enabled = !loading && preferred is { } option && eligible?.Contains(option.Id) == true;
        refreshButton.Enabled = !loading;
        repeatButton.Enabled = !loading && grid.CurrentRow?.DataBoundItem is AppointmentVisitContextRow { Group: "Recent" };
        repeatButton.Text = confirmRepeat.HasValue ? "Replace draft" : "Repeat selected visit";
    }

    private async void RepeatClicked(object? sender, EventArgs e)
    {
        if (!repeatButton.Enabled || repository is null ||
            grid.CurrentRow?.DataBoundItem is not AppointmentVisitContextRow row)
            return;
        if (replaceDraft && confirmRepeat != row.Id)
        {
            confirmRepeat = row.Id;
            notice.Text = "Confirm to replace the current draft with this visit's details.";
            UpdateActions();
            return;
        }
        loading = true;
        UpdateActions();
        var cancellation = lifetime.Token;
        try
        {
            var booking = await repository.ConfirmationAsync(row.Id, cancellation);
            if (cancellation.IsCancellationRequested)
                return;
            if (booking.CustomerId != customer || booking.ServiceId is null)
                throw new InvalidOperationException("This visit cannot be repeated. Check the customer and service.");
            RepeatDraft = booking.Rebook(true);
            DialogResult = DialogResult.OK;
            Close();
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch (Exception error) when (AppointmentsForm.IsExpected(error))
        {
            if (!cancellation.IsCancellationRequested)
                notice.Text = AppointmentsForm.Friendly(error);
        }
        finally
        {
            if (!cancellation.IsCancellationRequested)
            {
                loading = false;
                UpdateActions();
            }
        }
    }

    private void InspectClicked(object? sender, EventArgs e)
    {
        if (repository is null || grid.CurrentRow?.DataBoundItem is not AppointmentVisitContextRow row)
            return;
        using var dialog = new AppointmentConfirmationForm(repository, row.Id);
        dialog.ShowDialog(this);
    }

    private void SuggestionClicked(object? sender, EventArgs e)
    {
        if (!suggestionButton.Enabled || preferred is null)
            return;
        SuggestedProvider = preferred.Id;
        DialogResult = DialogResult.OK;
        Close();
    }

    private void ClosedContext(object? sender, FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
