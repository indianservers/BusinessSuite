using System.Data;
using Telerik.WinControls.UI;

namespace Business_Suite;

internal sealed partial class EmployeeProfileRequestsForm : Form
{
    private readonly EmployeeAdministrationRepository? repository;
    private readonly int employee;
    private readonly CancellationTokenSource lifetime = new();
    private bool busy;
    private bool writable;

    public EmployeeProfileRequestsForm() => InitializeComponent();

    internal EmployeeProfileRequestsForm(EmployeeAdministrationRepository repository, DataRow row) : this()
    {
        this.repository = repository;
        employee = row.Field<int>("id");
        heading.Text = $"{row["employee_name"]} · {row["employee_id"]}";
    }

    private DataRow? Selected => (grid.CurrentRow?.DataBoundItem as DataRowView)?.Row;

    private async void RequestsLoaded(object? sender, EventArgs e) => await RunAsync(ReadAsync);
    private async void RefreshClicked(object? sender, EventArgs e) => await RunAsync(ReadAsync);
    private async void FilterChanged(object? sender, EventArgs e)
    {
        if (Visible && !busy)
            await RunAsync(ReadAsync);
    }

    private async Task ReadAsync()
    {
        var requests = await repository!.ReadProfileRequestsAsync(employee, filter.SelectedItem?.Value as string ?? "", lifetime.Token);
        writable = requests.Writable;
        grid.DataSource = requests.Rows.DefaultView;
        status.Text = requests.Rows.Rows.Count == 0 ? "No profile change requests match this filter."
            : $"{requests.Rows.Rows.Count:N0} profile change requests";
    }

    private void SelectionChanged(object sender, CurrentRowChangedEventArgs e)
    {
        var selected = Selected;
        comparison.Text = selected?.Field<string>("comparison")?.Replace("\n", Environment.NewLine) ?? "";
        hint.Text = selected?.Field<bool>("supported") == false
            ? "This request includes fields that require the full approval workflow." : "";
        remarks.Text = "";
        UpdateActions();
    }

    private async void NewRequestClicked(object? sender, EventArgs e)
    {
        if (repository is null || !newRequest.Enabled)
            return;
        using var form = new EmployeeProfileRequestSubmitForm(repository, employee);
        if (form.ShowDialog(this) == DialogResult.OK)
            await RunAsync(ReadAsync);
    }

    private async void ApproveClicked(object? sender, EventArgs e) => await ReviewAsync(true);
    private async void RejectClicked(object? sender, EventArgs e) => await ReviewAsync(false);

    private async Task ReviewAsync(bool approving)
    {
        if (Selected is not DataRow row || !(approving ? approve.Enabled : reject.Enabled))
            return;
        await RunAsync(async () =>
        {
            await repository!.ReviewProfileRequestAsync(employee, row.Field<int>("id"), row.Field<string>("revision")!,
                approving, remarks.Text, lifetime.Token);
            await ReadAsync();
        });
    }

    private async Task RunAsync(Func<Task> action)
    {
        if (repository is null || busy)
            return;
        busy = true;
        UpdateActions();
        status.Text = "Working with profile requests…";
        try { await action(); }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or Npgsql.NpgsqlException or TimeoutException)
        {
            if (!lifetime.IsCancellationRequested)
                status.Text = error is InvalidOperationException or UnauthorizedAccessException ? error.Message
                    : "Could not update profile requests. Check PostgreSQL and retry.";
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
        var selected = Selected;
        bool canReview = !busy && writable && selected?.Field<bool>("can_review") == true &&
            selected.Field<string>("status") == "Pending";
        grid.Enabled = close.Enabled = refresh.Enabled = filter.Enabled = !busy;
        newRequest.Enabled = !busy && writable;
        remarks.Enabled = reject.Enabled = canReview;
        approve.Enabled = canReview && selected?.Field<bool>("supported") == true;
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
