using System.Data;

namespace Business_Suite;

internal sealed partial class EmployeeProfileHistoryForm : Form
{
    private readonly EmployeeAdministrationRepository? repository;
    private readonly int employee;
    private readonly CancellationTokenSource lifetime = new();

    public EmployeeProfileHistoryForm() => InitializeComponent();

    internal EmployeeProfileHistoryForm(EmployeeAdministrationRepository repository, DataRow row) : this()
    {
        this.repository = repository;
        employee = row.Field<int>("id");
        heading.Text = $"{row["employee_name"]} · {row["employee_id"]}";
    }

    private async void HistoryLoaded(object? sender, EventArgs e) => await LoadHistoryAsync();
    private async void RefreshClicked(object? sender, EventArgs e) => await LoadHistoryAsync();

    private async Task LoadHistoryAsync()
    {
        if (repository is null)
            return;
        refresh.Enabled = false;
        status.Text = "Loading profile history…";
        try
        {
            var history = await repository.ReadProfileHistoryAsync(employee, lifetime.Token);
            if (lifetime.IsCancellationRequested)
                return;
            grid.DataSource = history.DefaultView;
            status.Text = history.Rows.Count switch
            {
                0 => "No recorded profile changes.",
                200 => "Showing the most recent 200 profile changes.",
                _ => $"{history.Rows.Count:N0} profile changes"
            };
        }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or Npgsql.NpgsqlException or TimeoutException)
        {
            if (!lifetime.IsCancellationRequested)
            {
                grid.DataSource = null;
                status.Text = error is UnauthorizedAccessException or InvalidOperationException
                    ? error.Message : "Could not load profile history. Check PostgreSQL and retry.";
            }
        }
        finally
        {
            if (!lifetime.IsCancellationRequested)
                refresh.Enabled = true;
        }
    }

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        base.OnFormClosing(e);
        if (!e.Cancel)
            lifetime.Cancel();
    }
}
