using System.Data;
using Telerik.WinControls.UI;

namespace Business_Suite;

internal sealed partial class EmployeeMyProfileRequestsForm : Form
{
    private readonly DesktopDatabaseSettings? settings;
    private readonly EmployeeAdministrationRepository? repository;
    private readonly CancellationTokenSource lifetime = new();
    private bool busy;

    public EmployeeMyProfileRequestsForm() => InitializeComponent();

    internal EmployeeMyProfileRequestsForm(DesktopDatabaseSettings settings) : this()
    {
        this.settings = settings;
        repository = new EmployeeAdministrationRepository(settings);
    }

    private async void RequestsLoaded(object? sender, EventArgs e) => await ReadAsync();
    private async void RefreshClicked(object? sender, EventArgs e) => await ReadAsync();

    private async void FilterChanged(object? sender, EventArgs e)
    {
        if (Visible)
            await ReadAsync();
    }

    private async void NewRequestClicked(object? sender, EventArgs e)
    {
        if (settings is null || !newRequest.Enabled)
            return;
        using var form = new EmployeeProfileRequestSubmitForm(settings);
        if (form.ShowDialog(this) == DialogResult.OK)
            await ReadAsync(true);
    }

    private async Task ReadAsync(bool submitted = false)
    {
        if (repository is null || busy)
            return;
        busy = true;
        refresh.Enabled = filter.Enabled = newRequest.Enabled = false;
        if (submitted)
            filter.SelectedIndex = 3;
        status.Text = "Loading your change requests…";
        try
        {
            var history = await repository.ReadMyProfileRequestsAsync(filter.SelectedItem?.Value as string ?? "", lifetime.Token);
            if (lifetime.IsCancellationRequested)
                return;
            heading.Text = history.Employee;
            grid.DataSource = history.Rows.DefaultView;
            UpdateDetails();
            status.Text = submitted ? "Profile change request submitted." : history.Rows.Rows.Count switch
            {
                0 => "No change requests match this filter.",
                300 => "Showing the latest 300 change requests.",
                _ => $"{history.Rows.Rows.Count:N0} change requests"
            };
            newRequest.Enabled = history.CanSubmit;
        }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or Npgsql.NpgsqlException or TimeoutException)
        {
            if (!lifetime.IsCancellationRequested)
            {
                heading.Text = "";
                grid.DataSource = null;
                UpdateDetails();
                status.Text = error is InvalidOperationException or UnauthorizedAccessException
                    ? error.Message : "Could not load change requests. Check PostgreSQL and retry.";
            }
        }
        finally
        {
            busy = false;
            if (!lifetime.IsCancellationRequested)
                refresh.Enabled = filter.Enabled = true;
        }
    }

    private void SelectionChanged(object sender, CurrentRowChangedEventArgs e) => UpdateDetails();

    private void UpdateDetails()
    {
        var row = (grid.CurrentRow?.DataBoundItem as DataRowView)?.Row;
        reason.Text = row?.Field<string>("reason") ?? (row is null ? "" : "No reason provided.");
        reviewerNote.Text = row?.Field<string>("review_remarks") ?? "";
    }

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        base.OnFormClosing(e);
        if (!e.Cancel)
            lifetime.Cancel();
    }
}
