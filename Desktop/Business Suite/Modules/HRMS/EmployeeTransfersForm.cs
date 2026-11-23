using System.Data;
using Telerik.WinControls.UI;

namespace Business_Suite;

internal sealed partial class EmployeeTransfersForm : Form
{
    private readonly EmployeeAdministrationRepository? repository;
    private readonly int employee;
    private readonly CancellationTokenSource lifetime = new();
    private EmployeeTransferContext? context;
    private EmployeeTransferPreview? preview;
    private EmployeeTransferDraft? draft;
    private bool busy;

    public EmployeeTransfersForm() => InitializeComponent();

    internal EmployeeTransfersForm(EmployeeAdministrationRepository repository, int employee, string label) : this()
    {
        this.repository = repository;
        this.employee = employee;
        heading.Text = label;
    }

    internal bool Changed { get; private set; }
    private DataRow? Selected => (grid.CurrentRow?.DataBoundItem as DataRowView)?.Row;
    private int? Department => department.SelectedItem?.Value is int value ? value : (int?)null;
    private int? Designation => designation.SelectedItem?.Value is int value ? value : (int?)null;

    private async void TransfersLoaded(object? sender, EventArgs e) => await RunAsync(ReadAsync);
    private async void RefreshClicked(object? sender, EventArgs e) => await RunAsync(ReadAsync);

    private async Task ReadAsync()
    {
        context = await repository!.ReadTransfersAsync(employee, lifetime.Token);
        Fill(department, context.Departments.Rows.Cast<DataRow>(), context.CurrentDepartment);
        FillDesignations(context.CurrentDesignation);
        FillChangeOptions(manager, context.Managers, "manager");
        FillChangeOptions(shift, context.Shifts, "shift");
        effective.Value = context.Today;
        grid.DataSource = context.History.DefaultView;
        ResetPreview();
        status.Text = context.History.Rows.Count == 0 ? "No transfer history." : $"{context.History.Rows.Count:N0} transfer records";
    }

    private static void Fill(RadDropDownList dropDown, IEnumerable<DataRow> rows, int? selected)
    {
        dropDown.Items.Clear();
        dropDown.Items.Add(new RadListDataItem("Unassigned"));
        foreach (var row in rows)
            dropDown.Items.Add(new RadListDataItem(row.Field<string>("name")) { Value = row.Field<int>("id") });
        dropDown.SelectedIndex = 0;
        if (selected.HasValue)
            dropDown.SelectedValue = selected.Value;
    }

    private static void FillChangeOptions(RadDropDownList dropDown, DataTable rows, string label)
    {
        dropDown.Items.Clear();
        dropDown.Items.Add(new RadListDataItem($"Keep current {label}") { Value = -1 });
        dropDown.Items.Add(new RadListDataItem($"Clear {label}"));
        foreach (DataRow row in rows.Rows)
            dropDown.Items.Add(new RadListDataItem(row.Field<string>("name")) { Value = row.Field<int>("id") });
        dropDown.SelectedIndex = 0;
    }

    private void FillDesignations(int? selected)
    {
        if (context is not null)
            Fill(designation, context.Designations.Rows.Cast<DataRow>().Where(row => row.Field<int>("department_id") == Department), selected);
    }

    private void DepartmentChanged(object? sender, Telerik.WinControls.UI.Data.PositionChangedEventArgs e)
    {
        if (!busy)
            FillDesignations(null);
        ResetPreview();
    }

    private void InputsChanged(object? sender, EventArgs e) => ResetPreview();
    private void SelectionChanged(object sender, CurrentRowChangedEventArgs e) => UpdateActions();
    private void ResetPreview()
    {
        preview = null;
        draft = null;
        comparison.Text = "";
        save.Text = "Apply transfer";
        UpdateActions();
    }

    private async void PreviewClicked(object? sender, EventArgs e)
    {
        var proposed = new EmployeeTransferDraft(Department, Designation, effective.Value.Date, reason.Text,
            manager.SelectedIndex > 0, manager.SelectedItem?.Value is int id && id > 0 ? id : (int?)null,
            shift.SelectedIndex > 0, shift.SelectedItem?.Value is int shiftId && shiftId > 0 ? shiftId : (int?)null);
        await RunAsync(async () =>
        {
            preview = await repository!.PreviewTransferAsync(employee, proposed, lifetime.Token);
            draft = proposed;
            comparison.Text = $"{preview.Before} → {preview.After}";
            save.Text = preview.Scheduled ? "Schedule transfer" : "Apply transfer";
            status.Text = preview.Scheduled ? "Apply the transfer on or after its effective date." : "The transfer takes effect today.";
        });
    }

    private async void SaveClicked(object? sender, EventArgs e)
    {
        if (draft is null || preview is null)
            return;
        await RunAsync(async () =>
        {
            bool scheduled = preview.Scheduled;
            await repository!.SaveTransferAsync(employee, draft, preview.Revision, lifetime.Token);
            Changed = true;
            reason.Text = "";
            await ReadAsync();
            status.Text = scheduled ? "Transfer scheduled." : "Transfer applied.";
        });
    }

    private async void ApplyDueClicked(object? sender, EventArgs e)
    {
        if (Selected is not DataRow row || !applyDue.Enabled)
            return;
        await RunAsync(async () =>
        {
            await repository!.ApplyDueTransferAsync(employee, row.Field<int>("id"), row.Field<string>("revision")!, lifetime.Token);
            Changed = true;
            await ReadAsync();
            status.Text = "Scheduled transfer applied.";
        });
    }

    private async Task RunAsync(Func<Task> action)
    {
        if (repository is null || busy)
            return;
        busy = true;
        UpdateActions();
        status.Text = "Working with employee transfers…";
        try { await action(); }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or System.Text.Json.JsonException or Npgsql.NpgsqlException or TimeoutException)
        {
            if (!lifetime.IsCancellationRequested)
                status.Text = error is InvalidOperationException or UnauthorizedAccessException ? error.Message
                    : "Could not load or save the transfer. Check PostgreSQL and refresh.";
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
        close.Enabled = refresh.Enabled = grid.Enabled = !busy;
        editor.Enabled = !busy && context?.CanWrite == true;
        review.Enabled = editor.Enabled && reason.Text.Trim().Length >= 3;
        save.Enabled = editor.Enabled && preview is not null;
        applyDue.Enabled = editor.Enabled && Selected?.Field<bool>("due") == true;
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
