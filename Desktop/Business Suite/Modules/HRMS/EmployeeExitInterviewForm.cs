using System.Data;
using Telerik.WinControls.UI;

namespace Business_Suite;

internal sealed partial class EmployeeExitInterviewForm : Form
{
    private readonly EmployeeAdministrationRepository? repository;
    private readonly int employee;
    private readonly int exit;
    private readonly CancellationTokenSource lifetime = new();
    private bool writable;
    private bool busy;

    public EmployeeExitInterviewForm() => InitializeComponent();

    internal EmployeeExitInterviewForm(EmployeeAdministrationRepository repository, int employee, int exit, string label) : this()
    {
        this.repository = repository;
        this.employee = employee;
        this.exit = exit;
        heading.Text = label;
    }

    private async void InterviewsLoaded(object? sender, EventArgs e) => await RunAsync(ReadAsync);
    private async void RefreshClicked(object? sender, EventArgs e) => await RunAsync(ReadAsync);

    private async Task ReadAsync()
    {
        var result = await repository!.ReadExitInterviewsAsync(employee, exit, lifetime.Token);
        writable = result.CanAdd;
        grid.DataSource = result.Records.DefaultView;
        status.Text = result.Records.Rows.Count == 0 ? "No exit interviews." : $"{result.Records.Rows.Count:N0} exit interviews";
    }

    private void SelectionChanged(object sender, CurrentRowChangedEventArgs e)
    {
        var row = (grid.CurrentRow?.DataBoundItem as DataRowView)?.Row;
        details.Text = row is null ? "" : $"{row.Field<string>("feedback") ?? ""}{Environment.NewLine}{row.Field<string>("suggestions") ?? ""}";
    }

    private async void SaveClicked(object? sender, EventArgs e)
    {
        if (!save.Enabled)
            return;
        int? Rating(RadSpinEditor editor) => editor.Value == 0 ? (int?)null : (int)editor.Value;
        var draft = new EmployeeExitInterviewDraft(date.Checked ? date.Value.Date : (DateTime?)null, reason.Text,
            Rating(job), Rating(management), Rating(environment), Rating(growth),
            rejoin.SelectedIndex == 0 ? (bool?)null : rejoin.SelectedIndex == 1, feedback.Text, suggestions.Text);
        await RunAsync(async () =>
        {
            await repository!.AddExitInterviewAsync(employee, exit, draft, lifetime.Token);
            reason.Clear();
            job.Value = management.Value = environment.Value = growth.Value = 0;
            rejoin.SelectedIndex = 0;
            feedback.Clear();
            suggestions.Clear();
            date.Checked = false;
            await ReadAsync();
            status.Text = "Exit interview recorded.";
        });
    }

    private async Task RunAsync(Func<Task> work)
    {
        if (repository is null || busy)
            return;
        busy = true;
        SetActions();
        status.Text = "Working with exit interviews…";
        try { await work(); }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or Npgsql.NpgsqlException or TimeoutException)
        {
            if (!lifetime.IsCancellationRequested)
                status.Text = error is InvalidOperationException or UnauthorizedAccessException ? error.Message
                    : "Could not update exit interviews. Check PostgreSQL and retry.";
        }
        finally
        {
            busy = false;
            if (!lifetime.IsCancellationRequested)
                SetActions();
        }
    }

    private void SetActions()
    {
        grid.Enabled = close.Enabled = refresh.Enabled = !busy;
        editor.Enabled = save.Enabled = !busy && writable;
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
