namespace Business_Suite;

public sealed partial class AppointmentSlotPickerForm : Form
{
    private readonly AppointmentRepository? repository;
    private readonly AppointmentSlot? draft;
    private readonly int service;
    private readonly AppointmentKey? key;
    private readonly CancellationTokenSource lifetime = new();
    private bool ready;
    private bool busy;

    public AppointmentSlotPickerForm() => InitializeComponent();

    internal AppointmentSlotPickerForm(AppointmentRepository repository, int service, AppointmentSlot draft,
        AppointmentKey? key, List<AppointmentOption> providers) : this()
    {
        this.repository = repository;
        this.service = service;
        this.draft = draft;
        this.key = key;
        day.Value = draft.LocalTime.Date;
        providerPicker.DisplayMember = nameof(AppointmentOption.Name);
        providerPicker.ValueMember = nameof(AppointmentOption.Id);
        providerPicker.DataSource = providers;
        providerPicker.SelectedValue = draft.Provider;
    }

    internal DateTime? SelectedStart { get; private set; }
    internal int? SelectedProvider { get; private set; }

    private void PickerShown(object? sender, EventArgs e)
    {
        ready = true;
        LoadClicked(sender, e);
    }

    private async void LoadClicked(object? sender, EventArgs e)
    {
        if (!ready || busy || repository is null || draft is null ||
            providerPicker.SelectedValue is not int provider)
            return;
        busy = true;
        UpdateActions();
        var cancellation = lifetime.Token;
        notice.Text = "Loading provider times…";
        try
        {
            var page = await repository.ProviderSlotsAsync(draft with { Provider = provider, LocalTime = day.Value.Date }, key, cancellation);
            if (cancellation.IsCancellationRequested)
                return;
            grid.DataSource = page.Slots;
            notice.Text = page.Slots.Count == 0
                ? $"No candidate times on this day. Times use {page.Zone}."
                : $"Times use {page.Zone}. Check the selected time for all booking requirements.";
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch (Exception error) when (AppointmentsForm.IsExpected(error))
        {
            if (!cancellation.IsCancellationRequested)
            {
                grid.DataSource = null;
                notice.Text = AppointmentsForm.Friendly(error);
            }
        }
        finally
        {
            if (!cancellation.IsCancellationRequested)
            {
                busy = false;
                UpdateActions();
            }
        }
    }

    private async void SelectClicked(object? sender, EventArgs e)
    {
        if (busy || repository is null || draft is null || providerPicker.SelectedValue is not int provider ||
            grid.CurrentRow?.DataBoundItem is not AppointmentSlotChoice { Selectable: true } choice)
            return;
        busy = true;
        UpdateActions();
        var cancellation = lifetime.Token;
        notice.Text = "Checking service, provider and resources…";
        try
        {
            var selected = draft with { Provider = provider, LocalTime = choice.Starts };
            if (key is null)
                await repository.CheckAsync(service, selected, cancellation);
            else
                await repository.CheckRescheduleAsync(key, selected, cancellation);
            if (cancellation.IsCancellationRequested)
                return;
            SelectedStart = choice.Starts;
            SelectedProvider = provider;
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
                busy = false;
                UpdateActions();
            }
        }
    }

    private void GridSelectionChanged(object? sender, EventArgs e) => UpdateActions();

    private void UpdateActions()
    {
        if (selectButton is null)
            return;
        day.Enabled = providerPicker.Enabled = refreshButton.Enabled = !busy;
        selectButton.Enabled = !busy && grid.CurrentRow?.DataBoundItem is AppointmentSlotChoice { Selectable: true };
    }

    private void PickerClosed(object? sender, FormClosedEventArgs e)
    {
        lifetime.Cancel();
        lifetime.Dispose();
    }
}
