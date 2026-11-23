using System.Data;

namespace Business_Suite;

internal sealed partial class PmsSchedulePlanForm : Form
{
    private readonly PmsProjectRepository? repository;
    private readonly int project;
    private readonly CancellationTokenSource lifetime = new();
    private PmsSchedulePlan? preview;
    private PmsCalendarDraft? proposedCalendar;
    private PmsScheduleMove? proposedMove;
    private bool busy;
    private bool confirming;
    private bool restoringLevel;

    public PmsSchedulePlanForm() => InitializeComponent();

    internal PmsSchedulePlanForm(PmsProjectRepository repository, int project, string label) : this()
    {
        this.repository = repository;
        this.project = project;
        heading.Text = label;
    }

    private async void PlanLoaded(object? sender, EventArgs e) => await RunAsync(ReadAsync);
    private async void RefreshClicked(object? sender, EventArgs e) => await RunAsync(ReadAsync);

    private async Task ReadAsync()
    {
        preview = null;
        preview = await repository!.PreviewSchedulePlanAsync(project, lifetime.Token, proposedCalendar, proposedMove, level.Checked);
        grid.DataSource = preview.Rows.DefaultView;
        explanation.Text = preview.ResourceLeveling ? "Resource leveling uses project assignee capacity. Slack is unavailable."
            : "Zero slack identifies critical tasks. The preview uses the saved working days and holidays.";
        status.Text = preview.Finish is DateTime finish
            ? $"Finish {finish:d} · {preview.Changed:N0} proposed date changes · {preview.MissingDates:N0} tasks missing dates"
            : "Date at least one task to calculate a schedule plan.";
        if (preview.CalendarChanged)
            status.Text += " · Unsaved calendar preview";
        if (proposedMove is not null)
            status.Text += " · Proposed task move";
    }

    private async void LevelChanged(object? sender, EventArgs e)
    {
        if (!Visible || restoringLevel || busy)
            return;
        var previous = preview;
        await RunAsync(ReadAsync);
        if (preview is null && previous is not null)
        {
            restoringLevel = true;
            level.Checked = previous.ResourceLeveling;
            restoringLevel = false;
            preview = previous;
            UpdateActions();
        }
    }

    private async void CalendarClicked(object? sender, EventArgs e)
    {
        if (preview?.CanEditCalendar != true || !calendar.Enabled)
            return;
        using var editor = new PmsScheduleCalendarForm(preview.Calendar);
        if (editor.ShowDialog(this) != DialogResult.OK || editor.Calendar is null)
            return;
        var previous = proposedCalendar;
        var previousPreview = preview;
        proposedCalendar = editor.Calendar;
        await RunAsync(ReadAsync);
        if (preview is null)
        {
            proposedCalendar = previous;
            preview = previousPreview;
            UpdateActions();
        }
    }

    private async void MoveClicked(object? sender, EventArgs e)
    {
        if (preview?.CanEditCalendar != true || !moveTask.Enabled)
            return;
        using var editor = new PmsScheduleMoveForm(preview.Rows, proposedMove);
        var result = editor.ShowDialog(this);
        if (result is not (DialogResult.OK or DialogResult.Retry))
            return;
        var previous = proposedMove;
        var previousPreview = preview;
        proposedMove = result == DialogResult.OK ? editor.Proposal : null;
        await RunAsync(ReadAsync);
        if (preview is null)
        {
            proposedMove = previous;
            preview = previousPreview;
            UpdateActions();
        }
    }

    private void AllocationsClicked(object? sender, EventArgs e)
    {
        if (!allocations.Enabled || preview?.Allocations is not DataTable rows)
            return;
        using var details = new PmsResourceAllocationsForm(rows, heading.Text);
        details.ShowDialog(this);
    }

    private void ApplyClicked(object? sender, EventArgs e)
    {
        confirming = true;
        confirmation.Visible = true;
        UpdateActions();
    }

    private void CancelClicked(object? sender, EventArgs e)
    {
        confirming = false;
        confirmation.Visible = false;
        UpdateActions();
    }

    private async void ConfirmClicked(object? sender, EventArgs e)
    {
        if (!confirming || preview is null)
            return;
        confirming = false;
        confirmation.Visible = false;
        await RunAsync(async () =>
        {
            int changed = await repository!.ApplySchedulePlanAsync(project, preview.Revision, lifetime.Token, proposedCalendar, proposedMove, level.Checked);
            proposedCalendar = null;
            proposedMove = null;
            await ReadAsync();
            status.Text = $"Updated {changed:N0} task schedules.";
        });
    }

    private async Task RunAsync(Func<Task> work)
    {
        if (repository is null || busy || confirming)
            return;
        busy = true;
        UpdateActions();
        status.Text = "Calculating the dependency plan…";
        try { await work(); }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException or FormatException
            or System.Text.Json.JsonException or Npgsql.NpgsqlException or TimeoutException)
        {
            if (!lifetime.IsCancellationRequested)
                status.Text = error is InvalidOperationException or UnauthorizedAccessException ? error.Message
                    : "Could not load or apply the schedule plan. Check PostgreSQL and refresh.";
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
        refresh.Enabled = grid.Enabled = !busy && !confirming;
        close.Enabled = !busy;
        apply.Enabled = refresh.Enabled && preview?.CanApply == true;
        allocations.Enabled = refresh.Enabled && preview?.Allocations is not null;
        calendar.Enabled = refresh.Enabled && preview?.CanEditCalendar == true;
        moveTask.Enabled = level.Enabled = calendar.Enabled && preview!.Rows.Rows.Count > 0;
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
