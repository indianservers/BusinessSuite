using System.Globalization;
using Telerik.WinControls.UI;

namespace Business_Suite;

internal sealed partial class PmsPersonalHoursForm : Form
{
    private readonly PmsProjectRepository? repository;
    private readonly CancellationTokenSource lifetime = new();
    private PmsPersonalHours? settings;
    private bool busy;

    public PmsPersonalHoursForm() => InitializeComponent();

    internal PmsPersonalHoursForm(PmsProjectRepository repository) : this() => this.repository = repository;

    private (CheckBox Enabled, RadTextBox Start, RadTextBox End)[] Inputs() => new[]
    {
        (monday, mondayStart, mondayEnd), (tuesday, tuesdayStart, tuesdayEnd), (wednesday, wednesdayStart, wednesdayEnd),
        (thursday, thursdayStart, thursdayEnd), (friday, fridayStart, fridayEnd), (saturday, saturdayStart, saturdayEnd),
        (sunday, sundayStart, sundayEnd)
    };

    private async void HoursLoaded(object? sender, EventArgs e) => await RunAsync(LoadAsync);
    private async void RefreshClicked(object? sender, EventArgs e) => await RunAsync(LoadAsync);

    private async Task LoadAsync()
    {
        settings = await repository!.ReadMyWorkHoursAsync(lifetime.Token);
        var items = Inputs();
        foreach (var workday in settings.Workdays)
        {
            items[workday.Day].Enabled.Checked = workday.Enabled;
            items[workday.Day].Start.Text = workday.Start.ToString(@"hh\:mm", CultureInfo.InvariantCulture);
            items[workday.Day].End.Text = workday.End.ToString(@"hh\:mm", CultureInfo.InvariantCulture);
        }
        status.Text = settings.CanSave ? "Enter times in 24-hour HH:mm format." : "This branch is read-only.";
    }

    private async void SaveClicked(object? sender, EventArgs e)
    {
        if (settings is null || !save.Enabled)
            return;
        var items = Inputs();
        var workdays = new PmsPersonalWorkday[7];
        for (int day = 0; day < 7; day++)
        {
            var row = items[day];
            if (!TimeSpan.TryParseExact(row.Start.Text.Trim(), @"hh\:mm", CultureInfo.InvariantCulture, out var start) ||
                !TimeSpan.TryParseExact(row.End.Text.Trim(), @"hh\:mm", CultureInfo.InvariantCulture, out var end) ||
                (row.Enabled.Checked && end <= start))
            {
                status.Text = $"{row.Enabled.Text} requires valid HH:mm times. A working day must end after it starts.";
                return;
            }
            workdays[day] = new PmsPersonalWorkday(day, row.Enabled.Checked, start, end);
        }
        await RunAsync(async () =>
        {
            await repository!.SaveMyWorkHoursAsync(settings.Revision, workdays, lifetime.Token);
            await LoadAsync();
            status.Text = "Your working hours were saved.";
        });
    }

    private async Task RunAsync(Func<Task> action)
    {
        if (repository is null || busy)
            return;
        busy = true;
        UpdateActions();
        status.Text = "Working with calendar preferences…";
        try { await action(); }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or Npgsql.NpgsqlException or System.Text.Json.JsonException or TimeoutException)
        {
            if (!lifetime.IsCancellationRequested)
                status.Text = error is InvalidOperationException or UnauthorizedAccessException ? error.Message
                    : "Could not load or save working hours. Check PostgreSQL and retry.";
        }
        finally
        {
            busy = false;
            if (!lifetime.IsCancellationRequested)
                UpdateActions();
        }
    }

    private void UpdateActions()
    {
        editor.Enabled = save.Enabled = !busy && settings?.CanSave == true;
        close.Enabled = refresh.Enabled = !busy;
    }

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        base.OnFormClosing(e);
        if (busy)
            e.Cancel = true;
        if (!e.Cancel)
            lifetime.Cancel();
    }
}
