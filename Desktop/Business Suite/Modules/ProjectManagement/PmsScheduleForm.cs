using System.Data;
using Telerik.WinControls.UI;

namespace Business_Suite;

internal sealed partial class PmsScheduleForm : Form
{
    private readonly PmsProjectRepository? repository;
    private readonly int project;
    private readonly CancellationTokenSource lifetime = new();
    private bool busy;

    public PmsScheduleForm() => InitializeComponent();

    internal PmsScheduleForm(PmsProjectRepository repository, DataRow row) : this()
    {
        this.repository = repository;
        project = row.Field<int>("id");
        heading.Text = $"{row["project_key"]} · {row["name"]}";
    }

    private DataRow? Selected => (grid.CurrentRow?.DataBoundItem as DataRowView)?.Row;

    private async void ScheduleLoaded(object? sender, EventArgs e) => await RunAsync(() => ReadAsync());
    private async void RefreshClicked(object? sender, EventArgs e) => await RunAsync(() => ReadAsync());
    private async void FilterChanged(object? sender, EventArgs e)
    {
        if (Visible)
            await RunAsync(() => ReadAsync());
    }

    private void SelectionChanged(object sender, CurrentRowChangedEventArgs e)
    {
        var task = Selected;
        var first = task?.Field<DateTime?>("start_date");
        var last = task?.Field<DateTime?>("due_date");
        start.Value = first ?? DateTime.Today;
        start.Checked = first.HasValue;
        due.Value = last ?? DateTime.Today;
        due.Checked = last.HasValue;
        UpdateActions();
    }

    private async Task ReadAsync(int? select = null, bool saved = false)
    {
        var rows = await repository!.ReadProjectScheduleAsync(project, filter.SelectedItem?.Value as string ?? "", lifetime.Token);
        if (saved && filter.SelectedIndex > 0 && !rows.Rows.Cast<DataRow>().Any(row => row.Field<int>("id") == select))
        {
            filter.SelectedIndex = 0;
            rows = await repository.ReadProjectScheduleAsync(project, "", lifetime.Token);
        }
        grid.DataSource = rows.DefaultView;
        if (select.HasValue)
            grid.CurrentRow = grid.Rows.FirstOrDefault(row =>
                row.DataBoundItem is DataRowView bound && bound.Row.Field<int>("id") == select.Value);
        var changed = rows.Rows.Cast<DataRow>().FirstOrDefault(row => row.Field<int>("id") == select);
        long warnings = changed?.Field<long>("conflicts") ?? 0L;
        status.Text = saved && warnings > 0 ? $"Schedule saved. {warnings:N0} dependency date conflicts on this task."
            : saved ? "Schedule saved."
            : rows.Rows.Count == 0 ? "No tasks match this schedule filter." : $"{rows.Rows.Count:N0} tasks";
    }

    private async void SaveClicked(object? sender, EventArgs e)
    {
        if (Selected is not DataRow row || !save.Enabled)
            return;
        int task = row.Field<int>("id");
        DateTime? first = start.Checked ? start.Value.Date : (DateTime?)null;
        DateTime? last = due.Checked ? due.Value.Date : (DateTime?)null;
        await RunAsync(async () =>
        {
            await repository!.RescheduleTaskAsync(project, task, row.Field<string>("revision")!, first, last, lifetime.Token);
            await ReadAsync(task, true);
        });
    }

    private void ClearClicked(object? sender, EventArgs e) => start.Checked = due.Checked = false;

    private void CapacityClicked(object? sender, EventArgs e)
    {
        if (repository is null || busy)
            return;
        using var capacity = new PmsResourceCapacityForm(repository, project, heading.Text);
        capacity.ShowDialog(this);
    }

    private async void PlanClicked(object? sender, EventArgs e)
    {
        if (repository is null || busy)
            return;
        using var plan = new PmsSchedulePlanForm(repository, project, heading.Text);
        plan.ShowDialog(this);
        await RunAsync(() => ReadAsync());
    }

    private void BaselinesClicked(object? sender, EventArgs e)
    {
        if (repository is null || busy)
            return;
        using var baselines = new PmsScheduleBaselinesForm(repository, project, heading.Text);
        baselines.ShowDialog(this);
    }

    private async void DependenciesClicked(object? sender, EventArgs e)
    {
        if (Selected is not DataRow row)
            return;
        using var dependencies = new PmsDependenciesForm(repository!, row);
        dependencies.ShowDialog(this);
        await RunAsync(() => ReadAsync(row.Field<int>("id")));
    }

    private async Task RunAsync(Func<Task> work)
    {
        if (repository is null || busy)
            return;
        busy = true;
        UpdateActions();
        status.Text = "Working with the project schedule…";
        try { await work(); }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or Npgsql.NpgsqlException or TimeoutException)
        {
            if (!lifetime.IsCancellationRequested)
                status.Text = error is InvalidOperationException or UnauthorizedAccessException ? error.Message
                    : "Could not update the schedule. Check PostgreSQL and retry.";
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
        grid.Enabled = refresh.Enabled = filter.Enabled = close.Enabled = baselinesButton.Enabled = planButton.Enabled = capacityButton.Enabled = !busy;
        bool change = !busy && Selected?.Field<bool>("can_edit") == true;
        start.Enabled = due.Enabled = clear.Enabled = save.Enabled = change;
        dependenciesButton.Enabled = !busy && Selected is not null;
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
