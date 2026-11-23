using System.Data;

namespace Business_Suite;

internal sealed partial class EmployeeLifecycleForm : Form
{
    private readonly EmployeeAdministrationRepository? repository;
    private readonly CancellationTokenSource lifetime = new();
    private readonly int employee;
    private readonly string? revision;
    private readonly bool reactivate;
    private readonly bool linkedLogin;
    private readonly bool loginActive;
    private readonly bool writable;
    private bool ready;
    private bool saving;

    public EmployeeLifecycleForm() => InitializeComponent();

    internal EmployeeLifecycleForm(EmployeeAdministrationRepository repository, DataRow row) : this()
    {
        this.repository = repository;
        employee = row.Field<int>("id");
        revision = row.Field<string>("employment_revision");
        reactivate = EmployeeAdministrationRepository.IsDeparted(row.Field<string>("status"));
        linkedLogin = row.Field<bool>("linked_login");
        loginActive = row.Field<bool>("login_active");
        writable = row.Field<bool>("can_write");
        accessButton.Text = loginActive ? "Suspend login" : "Reactivate login";
        employeeLabel.Text = $"{row["employee_name"]} · {row["employee_id"]} · {row["status"]}";
        applyButton.Text = reactivate ? "Reactivate employment" : "Terminate employment";
        reasonInput.Enabled = writable;
    }

    private async void LifecycleLoaded(object? sender, EventArgs e)
    {
        if (repository is null)
            return;
        statusLabel.Text = "Loading lifecycle history…";
        try
        {
            var history = await repository.ListLifecycleAsync(employee, lifetime.Token);
            if (lifetime.IsCancellationRequested)
                return;
            historyGrid.DataSource = history.DefaultView;
            ready = true;
            statusLabel.Text = !writable ? "This branch has read-only access."
                : reactivate && linkedLogin ? "Employment returns to Active. Login access is managed separately."
                : reactivate ? "Reactivation restores Active status and clears the exit date."
                : linkedLogin ? "Termination takes effect today, disables the linked login and revokes its sessions."
                : "Termination takes effect today and retains the employee’s history.";
            SetActions();
        }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or Npgsql.NpgsqlException or TimeoutException)
        {
            if (!lifetime.IsCancellationRequested)
                statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException
                    ? error.Message : "Could not load employee lifecycle history from PostgreSQL.";
        }
    }

    private void ReasonChanged(object? sender, EventArgs e) => SetActions();

    private void SetActions()
    {
        applyButton.Enabled = ready && writable && !saving && reasonInput.Text.Trim().Length >= 3;
        accessButton.Enabled = applyButton.Enabled && linkedLogin && (loginActive || !reactivate);
        reasonInput.Enabled = writable && !saving;
        closeButton.Enabled = transfersButton.Enabled = onboardingButton.Enabled = exitButton.Enabled = !saving;
    }

    private void ExitClicked(object? sender, EventArgs e)
    {
        if (repository is null || saving)
            return;
        using var exit = new EmployeeExitForm(repository, employee, employeeLabel.Text);
        exit.ShowDialog(this);
        if (exit.Changed)
            DialogResult = DialogResult.OK;
    }

    private void OnboardingClicked(object? sender, EventArgs e)
    {
        if (repository is null || saving)
            return;
        using var onboarding = new EmployeeOnboardingForm(repository, employee, employeeLabel.Text);
        onboarding.ShowDialog(this);
        if (onboarding.Changed)
            DialogResult = DialogResult.OK;
    }

    private void TransfersClicked(object? sender, EventArgs e)
    {
        if (repository is null || saving)
            return;
        using var transfers = new EmployeeTransfersForm(repository, employee, employeeLabel.Text);
        transfers.ShowDialog(this);
        if (transfers.Changed)
            DialogResult = DialogResult.OK;
    }

    private async void ApplyClicked(object? sender, EventArgs e) => await ApplyAsync(false);

    private async void AccessClicked(object? sender, EventArgs e) => await ApplyAsync(true);

    private async Task ApplyAsync(bool loginOnly)
    {
        if (repository is null || revision is null || !(loginOnly ? accessButton.Enabled : applyButton.Enabled))
            return;
        saving = true;
        SetActions();
        statusLabel.Text = loginOnly ? "Saving login change…" : "Saving employment change…";
        bool applied = false;
        try
        {
            if (loginOnly)
                await repository.ChangeLoginAccessAsync(employee, revision, !loginActive, reasonInput.Text, lifetime.Token);
            else
                await repository.ChangeEmploymentAsync(employee, revision, reactivate, reasonInput.Text, lifetime.Token);
            applied = true;
        }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or Npgsql.NpgsqlException or TimeoutException)
        {
            statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException
                ? error.Message : "Could not save the change. Check PostgreSQL and retry.";
        }
        finally
        {
            saving = false;
            SetActions();
        }
        if (applied)
            DialogResult = DialogResult.OK;
    }

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        base.OnFormClosing(e);
        if (saving)
            e.Cancel = true;
        if (!e.Cancel)
            lifetime.Cancel();
    }
}
