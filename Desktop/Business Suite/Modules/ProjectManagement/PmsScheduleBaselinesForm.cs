using System.Data;
using System.Globalization;
using System.Text;

namespace Business_Suite;

internal sealed partial class PmsScheduleBaselinesForm : Form
{
    private readonly PmsProjectRepository? repository;
    private readonly int project;
    private readonly CancellationTokenSource lifetime = new();
    private PmsBaselineView? baseline;
    private bool busy;

    public PmsScheduleBaselinesForm() => InitializeComponent();

    internal PmsScheduleBaselinesForm(PmsProjectRepository repository, int project, string label) : this()
    {
        this.repository = repository;
        this.project = project;
        heading.Text = label;
    }

    private async void BaselinesLoaded(object? sender, EventArgs e) => await RunAsync(() => ReadAsync());
    private async void RefreshClicked(object? sender, EventArgs e) => await RunAsync(() => ReadAsync());
    private async void BaselineChanged(object? sender, EventArgs e)
    {
        if (Visible)
            await RunAsync(() => ReadAsync());
    }

    private void NameChanged(object? sender, EventArgs e) => UpdateActions();

    private async Task ReadAsync(string? select = null)
    {
        string? pick = select ?? (choice.SelectedItem?.Value as string);
        baseline = await repository!.ReadBaselinesAsync(project, string.IsNullOrEmpty(pick) ? null : pick, lifetime.Token);
        var list = new[] { new PmsBaselineOption("", "Latest baseline", "") }.Concat(Enumerable.Reverse(baseline.Options)).ToArray();
        choice.DataSource = null;
        choice.DisplayMember = nameof(PmsBaselineOption.Label);
        choice.ValueMember = nameof(PmsBaselineOption.Id);
        choice.DataSource = list;
        choice.SelectedValue = pick ?? "";
        grid.DataSource = baseline.Variance.DefaultView;
        var selected = baseline.Selected;
        status.Text = selected is null ? "No schedule baseline has been captured." :
            $"{selected.Name} · {baseline.RemovedCount:N0} captured tasks removed from the active schedule";
    }

    private async void CaptureClicked(object? sender, EventArgs e)
    {
        if (baseline is null || !capture.Enabled)
            return;
        await RunAsync(async () =>
        {
            string id = await repository!.CaptureBaselineAsync(project, name.Text, baseline.Revision, lifetime.Token);
            name.Text = "";
            await ReadAsync(id);
        });
    }

    private async void ExportClicked(object? sender, EventArgs e)
    {
        if (baseline is null || !export.Enabled || exportDialog.ShowDialog(this) != DialogResult.OK)
            return;
        await RunAsync(async () =>
        {
            string? selectedId = baseline?.Selected?.Id;
            var fresh = await repository!.ReadBaselinesAsync(project, selectedId, lifetime.Token);
            if (!fresh.CanExport || fresh.Selected is not PmsBaselineOption selected)
                throw new UnauthorizedAccessException("Schedule variance export is unavailable in this scope.");
            using var output = new StreamWriter(exportDialog.FileName, false, new UTF8Encoding(true));
            await output.WriteLineAsync("Baseline,Captured at,Task,Title,Baseline due,Current due,Variance calendar days,In baseline");
            foreach (DataRow row in fresh.Variance.Rows)
            {
                string Date(string key) => row.Field<DateTime?>(key)?.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture) ?? "";
                string[] cells = { selected.Name, selected.CapturedAt, row.Field<string>("task_key") ?? "", row.Field<string>("title") ?? "",
                    Date("baseline_due_date"), Date("due_date") };
                string days = row.Field<int?>("due_variance_days")?.ToString(CultureInfo.InvariantCulture) ?? "";
                await output.WriteLineAsync(string.Join(",", cells.Select(PmsGridExport.Escape)) + "," + days + "," +
                    (row.Field<bool>("in_baseline") ? "True" : "False"));
            }
            status.Text = "Schedule variance exported.";
        });
    }

    private async Task RunAsync(Func<Task> work)
    {
        if (repository is null || busy)
            return;
        busy = true;
        UpdateActions();
        status.Text = "Working with schedule baselines…";
        try { await work(); }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException or IOException
            or System.Text.Json.JsonException or Npgsql.NpgsqlException or TimeoutException)
        {
            if (!lifetime.IsCancellationRequested)
                status.Text = error is InvalidOperationException or UnauthorizedAccessException ? error.Message
                    : "Could not load or save the schedule baseline. Check PostgreSQL and retry.";
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
        choice.Enabled = refresh.Enabled = close.Enabled = !busy;
        name.Enabled = !busy && baseline?.CanCapture == true;
        capture.Enabled = name.Enabled && !string.IsNullOrWhiteSpace(name.Text);
        export.Enabled = !busy && baseline?.CanExport == true;
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
