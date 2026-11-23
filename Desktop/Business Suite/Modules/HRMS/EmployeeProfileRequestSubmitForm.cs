namespace Business_Suite;

internal sealed partial class EmployeeProfileRequestSubmitForm : Form
{
    private readonly EmployeeAdministrationRepository? repository;
    private readonly int? employee;
    private readonly CancellationTokenSource lifetime = new();
    private EmployeeRequestSnapshot? snapshot;
    private bool busy;

    public EmployeeProfileRequestSubmitForm() => InitializeComponent();

    internal EmployeeProfileRequestSubmitForm(DesktopDatabaseSettings settings)
        : this(new EmployeeAdministrationRepository(settings), null) { }

    internal EmployeeProfileRequestSubmitForm(EmployeeAdministrationRepository repository, int? employee) : this()
    {
        this.repository = repository;
        this.employee = employee;
    }

    private async void SubmitLoaded(object? sender, EventArgs e) => await ReloadAsync();
    private async void RefreshClicked(object? sender, EventArgs e) => await ReloadAsync();
    private void FieldChanged(object? sender, EventArgs e) => UpdateField();

    private void UpdateField()
    {
        current.Text = snapshot is not null && field.SelectedItem?.Value is string key ? snapshot.Values[key] ?? "" : "";
        proposed.Text = current.Text;
    }

    private async Task ReloadAsync()
    {
        await RunAsync(async () =>
        {
            snapshot = await repository!.ReadRequestSubmissionAsync(employee, lifetime.Token);
            heading.Text = snapshot.Name;
            if (field.SelectedIndex < 0)
                field.SelectedIndex = 0;
            UpdateField();
            status.Text = "Your requested value will be sent for review.";
        });
    }

    private async void SubmitClicked(object? sender, EventArgs e)
    {
        if (snapshot is null || field.SelectedItem?.Value is not string key || !submit.Enabled)
            return;
        bool submitted = false;
        await RunAsync(async () =>
        {
            await repository!.SubmitProfileRequestAsync(employee, snapshot.Revision, key, proposed.Text, reason.Text, lifetime.Token);
            submitted = true;
        });
        if (submitted)
            DialogResult = DialogResult.OK;
    }

    private async Task RunAsync(Func<Task> action)
    {
        if (repository is null || busy)
            return;
        busy = true;
        UpdateActions();
        status.Text = "Working with the employee profile…";
        try { await action(); }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is UnauthorizedAccessException or InvalidOperationException
            or Npgsql.NpgsqlException or TimeoutException)
        {
            if (!lifetime.IsCancellationRequested)
                status.Text = error is UnauthorizedAccessException or InvalidOperationException ? error.Message
                    : "Could not load or submit the profile change. Check PostgreSQL and retry.";
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
        editor.Enabled = submit.Enabled = !busy && snapshot is not null;
        refresh.Enabled = close.Enabled = !busy;
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
