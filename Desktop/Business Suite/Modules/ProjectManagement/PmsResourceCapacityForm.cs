using System.Data;
using System.Globalization;

namespace Business_Suite;

internal sealed partial class PmsResourceCapacityForm : Form
{
    private readonly PmsProjectRepository? repository;
    private readonly int project;
    private readonly CancellationTokenSource lifetime = new();
    private PmsCapacityWeek? current;
    private bool busy;

    public PmsResourceCapacityForm() => InitializeComponent();

    internal PmsResourceCapacityForm(PmsProjectRepository repository, int project, string label) : this()
    {
        this.repository = repository;
        this.project = project;
        heading.Text = label;
        var today = DateTime.Today;
        week.Value = today.AddDays(-(((int)today.DayOfWeek + 6) % 7));
    }

    private async void CapacityLoaded(object? sender, EventArgs e)
    {
        await RunAsync(async () =>
        {
            var people = await repository!.ReadCapacityPeopleAsync(project, lifetime.Token);
            person.DisplayMember = "name";
            person.ValueMember = "id";
            person.DataSource = people;
            person.SelectedIndex = -1;
            status.Text = people.Rows.Count == 0 ? "No eligible people are available in this project." : "Choose a person and week.";
        });
    }

    private void InputsChanged(object? sender, EventArgs e)
    {
        current = null;
        grid.DataSource = null;
        hours.Text = "";
        available.Text = "";
        if (!busy)
            status.Text = "Preview availability before saving a weekly baseline.";
        UpdateActions();
    }

    private async void PreviewClicked(object? sender, EventArgs e) => await RunAsync(ReadAsync);

    private async Task ReadAsync()
    {
        if (person.SelectedValue is not int selected)
            return;
        current = null;
        current = await repository!.ReadCapacityWeekAsync(project, selected, week.Value.Date, lifetime.Token);
        grid.DataSource = current.Days.DefaultView;
        decimal total = current.Days.Rows.Cast<DataRow>().Sum(row => row.Field<decimal>("hours"));
        available.Text = $"{total:N2} hours available";
        hours.Text = current.Override?.ToString("0.##", CultureInfo.CurrentCulture) ?? "";
        status.Text = current.Override.HasValue ? "Dated baseline loaded." : "No dated baseline. Using the person's working hours.";
    }

    private async void SaveClicked(object? sender, EventArgs e)
    {
        if (current?.CanSave != true || person.SelectedValue is not int selected)
            return;
        if (!decimal.TryParse(hours.Text, NumberStyles.Number, CultureInfo.CurrentCulture, out decimal value))
        {
            status.Text = "Enter weekly capacity from 0 to 168 hours.";
            return;
        }
        string? revision = current.Revision;
        await RunAsync(async () =>
        {
            await repository!.SaveCapacityWeekAsync(project, selected, week.Value.Date, value, revision, lifetime.Token);
            await ReadAsync();
            status.Text = "Dated capacity saved.";
        });
    }

    private async Task RunAsync(Func<Task> work)
    {
        if (busy || repository is null)
            return;
        busy = true;
        UpdateActions();
        status.Text = "Working with resource capacity…";
        try { await work(); }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException or
            Npgsql.NpgsqlException or System.Text.Json.JsonException or TimeoutException)
        {
            if (!lifetime.IsCancellationRequested)
                status.Text = error is InvalidOperationException or UnauthorizedAccessException
                    ? error.Message : "Could not load or save capacity. Check PostgreSQL and retry.";
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
        close.Enabled = person.Enabled = week.Enabled = !busy;
        preview.Enabled = !busy && person.SelectedValue is int;
        hours.Enabled = save.Enabled = !busy && current?.CanSave == true;
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
