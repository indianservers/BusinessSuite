using System.Data;

namespace Business_Suite;

internal sealed partial class EmployeeProfileChecksForm : Form
{
    private readonly EmployeeAdministrationRepository? repository;
    private readonly int employee;
    private readonly DataRow? employeeRow;
    private readonly CancellationTokenSource lifetime = new();

    public EmployeeProfileChecksForm() => InitializeComponent();

    internal EmployeeProfileChecksForm(EmployeeAdministrationRepository repository, DataRow row) : this()
    {
        this.repository = repository;
        employee = row.Field<int>("id");
        employeeRow = row;
        heading.Text = $"{row["employee_name"]} · {row["employee_id"]}";
    }

    private async void ChecksLoaded(object? sender, EventArgs e) => await LoadChecksAsync();
    private async void ReminderChanged(object? sender, Telerik.WinControls.UI.Data.PositionChangedEventArgs e)
    {
        if (refresh.Enabled && Visible)
            await LoadChecksAsync();
    }

    private async void CertificationsClicked(object? sender, EventArgs e)
    {
        if (repository is null || employeeRow is null || !refresh.Enabled)
            return;
        using var editor = new EmployeeCertificationForm(repository, employeeRow);
        editor.ShowDialog(this);
        await LoadChecksAsync();
    }

    private async void RequestsClicked(object? sender, EventArgs e)
    {
        if (repository is null || employeeRow is null || !refresh.Enabled)
            return;
        using var review = new EmployeeProfileRequestsForm(repository, employeeRow);
        review.ShowDialog(this);
        await LoadChecksAsync();
    }

    private async void RefreshClicked(object? sender, EventArgs e) => await LoadChecksAsync();

    private async Task LoadChecksAsync()
    {
        if (repository is null)
            return;
        refresh.Enabled = reminder.Enabled = false;
        status.Text = "Loading profile checks…";
        try
        {
            var history = await repository.ReadProfileChecksAsync(employee, reminder.SelectedItem?.Value is int days ? days : 90, lifetime.Token);
            if (lifetime.IsCancellationRequested)
                return;
            grid.DataSource = history.DefaultView;
            bool hasExpiring = history.Rows.Cast<DataRow>().Any(row => Equals(row["category"], "Certification expiry"));
            status.Text = hasExpiring ? $"{history.Rows.Count:N0} profile checks" : "No certifications expire within the selected window.";
        }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or Npgsql.NpgsqlException or TimeoutException)
        {
            if (!lifetime.IsCancellationRequested)
            {
                grid.DataSource = null;
                status.Text = error is UnauthorizedAccessException or InvalidOperationException
                    ? error.Message : "Could not load profile checks. Check PostgreSQL and retry.";
            }
        }
        finally
        {
            if (!lifetime.IsCancellationRequested)
                refresh.Enabled = reminder.Enabled = true;
        }
    }

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        base.OnFormClosing(e);
        if (!e.Cancel)
            lifetime.Cancel();
    }
}

