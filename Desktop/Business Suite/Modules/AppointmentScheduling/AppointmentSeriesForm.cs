using System.ComponentModel;
using System.Security.Cryptography;
using Npgsql;

namespace Business_Suite;

public sealed partial class AppointmentSeriesForm : Form
{
    private sealed class SeriesRow(AppointmentSeriesOccurrence occurrence)
    {
        public int Index => occurrence.Index;
        public DateTime LocalTime => occurrence.LocalTime;
        public string Status => occurrence.Status;
        public bool Available => occurrence.Available;
        public bool Include { get; set; } = occurrence.Available;
    }

    private static readonly int[] Intervals = [1, 7, 14];
    private readonly AppointmentRepository? repository;
    private readonly AppointmentDraft? draft;
    private ProtectedAppointmentJournal<AppointmentSeriesRequest>? journal;
    private FileStream? held;
    private AppointmentSeriesRequest? pending;
    private AppointmentSeriesRequest? preview;
    private BindingList<SeriesRow>? rows;
    private bool busy;
    internal AppointmentSeriesSaved? Saved { get; private set; }
    internal DateTime? AgendaDate { get; private set; }

    public AppointmentSeriesForm()
    {
        InitializeComponent();
        intervalBox.SelectedIndex = 1;
    }

    internal AppointmentSeriesForm(AppointmentRepository repository, AppointmentDraft? draft, string zone) : this()
    {
        this.repository = repository;
        this.draft = draft;
        timezoneLabel.Text = string.IsNullOrWhiteSpace(zone) ? "Dates use the provider timezone." : $"Provider timezone: {zone}";
    }

    private async void SeriesShown(object? sender, EventArgs e) => await RunAsync(() =>
    {
        journal = repository!.SeriesJournal();
        held = journal.Acquire();
        try { pending = journal.Read(); }
        catch
        {
            held.Dispose();
            held = null;
            throw;
        }
        if (pending is { } saved)
        {
            countBox.Value = saved.Count;
            intervalBox.SelectedIndex = Array.IndexOf(Intervals, saved.Interval);
            feedback.Text = "The original series is retained. Check its status or retry that request.";
        }
        return Task.CompletedTask;
    });

    private void InputChanged(object? sender, EventArgs e)
    {
        preview = null;
        rows = null;
        grid.DataSource = null;
        UpdateButtons();
    }

    private async void PreviewClicked(object? sender, EventArgs e) => await RunAsync(async () =>
    {
        if (draft is null || pending is not null)
            return;
        int interval = Intervals[intervalBox.SelectedIndex];
        var request = new AppointmentSeriesRequest(Guid.NewGuid(), draft, (int)countBox.Value, interval, []);
        var occurrences = await repository!.PreviewSeriesAsync(request, default);
        rows = new BindingList<SeriesRow>(occurrences.Select(item => new SeriesRow(item)).ToList());
        grid.DataSource = rows;
        preview = request;
        feedback.Text = "Available dates are selected. Confirmation checks them again and reserves them together.";
    });

    private void BeginCellEdit(object? sender, Telerik.WinControls.UI.GridViewCellCancelEventArgs e)
    {
        if (e.Row.DataBoundItem is not SeriesRow { Available: true } || busy || pending is not null || Saved is not null)
            e.Cancel = true;
    }

    private async void SaveClicked(object? sender, EventArgs e) => await RunAsync(async () =>
    {
        grid.EndEdit();
        if (journal is null || held is null)
            return;
        if (pending is null && preview is { } input && rows is not null)
        {
            var request = input with { Included = rows.Where(row => row.Available && row.Include).Select(row => row.Index).ToArray() };
            journal.Save(request);
            pending = request;
        }
        if (pending is not { } attempt)
            return;
        try
        {
            Complete(attempt, await repository!.SaveSeriesAsync(attempt, default));
        }
        catch (Exception error) when (error is ArgumentException or InvalidOperationException or UnauthorizedAccessException)
        {
            if (await repository!.CheckSeriesAsync(attempt, default) is null)
            {
                journal.Clear();
                pending = null;
                InputChanged(this, EventArgs.Empty);
            }
            throw;
        }
    });

    private async void CheckClicked(object? sender, EventArgs e) => await RunAsync(async () =>
    {
        if (pending is not { } attempt)
            return;
        if (await repository!.CheckSeriesAsync(attempt, default) is { } existing)
            Complete(attempt, existing);
        else
            feedback.Text = "No confirmed series was found. Retry the original request.";
    });

    private void Complete(AppointmentSeriesRequest attempt, AppointmentSeriesSaved confirmed)
    {
        Saved = confirmed;
        AgendaDate = attempt.Base.Slot.LocalTime.Date.AddDays(attempt.Included.Min() * attempt.Interval);
        journal!.Clear();
        pending = null;
        resultLabel.Text = $"Series #{confirmed.Id} confirmed. Bookings " + string.Join(", ", confirmed.Bookings.Select(id => "#" + id));
        feedback.Text = "All selected occurrences were reserved together.";
        closeButton.Text = "Done";
    }

    private async Task RunAsync(Func<Task> action)
    {
        if (repository is null || busy)
            return;
        busy = true;
        UpdateButtons();
        try { await action(); }
        catch (Exception error) when (AppointmentsForm.IsExpected(error) || error is CryptographicException)
        {
            feedback.Text = pending is not null && error is NpgsqlException or TimeoutException
                ? "Save outcome unknown. Check request status or retry the original request."
                : error is CryptographicException or IOException
                    ? "Series recovery could not be stored or opened for this Windows account."
                    : AppointmentsForm.Friendly(error);
        }
        finally
        {
            busy = false;
            UpdateButtons();
        }
    }

    private void UpdateButtons()
    {
        bool available = !busy && held is not null && Saved is null;
        countBox.Enabled = intervalBox.Enabled = previewButton.Enabled = available && pending is null && draft is not null;
        checkButton.Visible = pending is not null;
        checkButton.Enabled = available && pending is not null;
        saveButton.Enabled = available && (pending is not null || rows?.Any(row => row.Available) == true);
        saveButton.Text = pending is null ? "Confirm selected dates" : "Retry original request";
        closeButton.Enabled = !busy;
    }

    private void SeriesClosing(object? sender, FormClosingEventArgs e) => e.Cancel = busy;
    private void SeriesClosed(object? sender, FormClosedEventArgs e) => held?.Dispose();
}
