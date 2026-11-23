using System.Data;
using Telerik.WinControls.UI;

namespace Business_Suite;

internal sealed partial class EmployeeExitForm : Form
{
    private readonly EmployeeAdministrationRepository? repository;
    private readonly int employee;
    private readonly CancellationTokenSource lifetime = new();
    private EmployeeExitView? view;
    private bool busy;
    private bool confirmClose;
    internal bool Changed { get; private set; }

    public EmployeeExitForm() => InitializeComponent();

    internal EmployeeExitForm(EmployeeAdministrationRepository repository, int employee, string label) : this()
    {
        this.repository = repository;
        this.employee = employee;
        heading.Text = label;
    }

    private DataRow? Selected => (grid.CurrentRow?.DataBoundItem as DataRowView)?.Row;
    private async void ExitLoaded(object? sender, EventArgs e) => await RunAsync(ReadAsync);
    private async void RefreshClicked(object? sender, EventArgs e) => await RunAsync(ReadAsync);
    private void SelectionChanged(object sender, CurrentRowChangedEventArgs e) => UpdateActions();
    private void InputChanged(object? sender, EventArgs e) => UpdateActions();

    private async Task ReadAsync()
    {
        view = await repository!.ReadExitAsync(employee, lifetime.Token);
        grid.DataSource = view.Tasks.DefaultView;
        lastDay.Value = view.LastDay ?? view.Today;
        progress.Text = view.Status is null ? "No exit case." : $"{view.Status} · Last working day {view.LastDay:d}";
        status.Text = view.Tasks.Rows.Count == 0 ? "No exit checklist items." : $"{view.Tasks.Rows.Count:N0} clearance items";
    }

    private async void StartClicked(object? sender, EventArgs e)
    {
        if (!start.Enabled)
            return;
        await RunAsync(async () =>
        {
            await repository!.StartExitAsync(employee, lastDay.Value.Date, exitType.Text, reason.Text, lifetime.Token);
            reason.Clear();
            await ReadAsync();
            status.Text = "Exit checklist created.";
        });
    }

    private async void CompleteClicked(object? sender, EventArgs e)
    {
        if (Selected is not DataRow item || !complete.Enabled)
            return;
        await RunAsync(async () =>
        {
            await repository!.CompleteExitItemAsync(employee, item.Field<int>("id"), item.Field<string>("revision")!,
                reason.Text, lifetime.Token);
            reason.Clear();
            await ReadAsync();
            status.Text = "Clearance evidence recorded.";
        });
    }

    private void InterviewsClicked(object? sender, EventArgs e)
    {
        if (repository is null || view?.Case is not int record || !interviews.Enabled)
            return;
        using var history = new EmployeeExitInterviewForm(repository, employee, record, heading.Text);
        history.ShowDialog(this);
    }

    private async void SettlementsClicked(object? sender, EventArgs e)
    {
        if (repository is null || view?.Case is not int record || !settlements.Enabled)
            return;
        using var dialog = new EmployeeSettlementsForm(repository, employee, record, heading.Text);
        dialog.ShowDialog(this);
        if (dialog.Changed)
            await RunAsync(ReadAsync);
    }

    private async void ApproveClicked(object? sender, EventArgs e) => await DecideAsync(false);

    private void CloseExitClicked(object? sender, EventArgs e)
    {
        if (!closeExit.Enabled)
            return;
        confirmClose = true;
        confirmation.Visible = true;
        UpdateActions();
    }

    private async void ConfirmClicked(object? sender, EventArgs e)
    {
        if (!confirmClose)
            return;
        CancelCloseClicked(sender, e);
        await DecideAsync(true);
    }

    private void CancelCloseClicked(object? sender, EventArgs e)
    {
        confirmClose = false;
        confirmation.Visible = false;
        UpdateActions();
    }

    private async Task DecideAsync(bool completeExit)
    {
        if (view?.Case is not int record || view.Revision is not string revision)
            return;
        await RunAsync(async () =>
        {
            await repository!.DecideExitAsync(employee, record, revision, completeExit, lifetime.Token);
            Changed = true;
            await ReadAsync();
            status.Text = completeExit ? "Exit completed." : "Exit approved.";
        });
    }

    private async Task RunAsync(Func<Task> work)
    {
        if (repository is null || busy)
            return;
        busy = true;
        UpdateActions();
        status.Text = "Working with employee exit…";
        try { await work(); }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or Npgsql.NpgsqlException or TimeoutException)
        {
            if (!lifetime.IsCancellationRequested)
                status.Text = error is InvalidOperationException or UnauthorizedAccessException ? error.Message
                    : "Could not update employee exit. Check PostgreSQL and retry.";
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
        bool ready = !busy && !confirmClose;
        grid.Enabled = refresh.Enabled = ready;
        close.Enabled = !busy;
        interviews.Enabled = ready && view?.Case.HasValue == true;
        settlements.Enabled = interviews.Enabled;
        approve.Enabled = ready && view?.CanApprove == true;
        closeExit.Enabled = ready && view?.CanClose == true;
        bool starting = ready && view?.CanStart == true;
        bool clearing = ready && view?.CanComplete == true && Selected?.Field<bool>("is_completed") == false;
        lastDay.Enabled = exitType.Enabled = starting;
        reason.Enabled = starting || clearing;
        start.Enabled = starting && reason.Text.Trim().Length >= 3;
        complete.Enabled = clearing && reason.Text.Trim().Length >= 3;
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
