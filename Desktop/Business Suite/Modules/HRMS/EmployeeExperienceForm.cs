using System.Data;

using Telerik.WinControls.UI;

namespace Business_Suite;

internal sealed partial class EmployeeExperienceForm : Form
{
    private readonly EmployeeAdministrationRepository? repository;
    private readonly CancellationTokenSource lifetime = new();
    private readonly int employee;
    private readonly bool writable;
    private int? editing;
    private string? revision;
    private bool busy;

    public EmployeeExperienceForm() => InitializeComponent();

    internal EmployeeExperienceForm(EmployeeAdministrationRepository repository, DataRow row) : this()
    {
        this.repository = repository;
        employee = row.Field<int>("id");
        writable = row.Field<bool>("can_write");
        heading.Text = $"{row["employee_name"]} · {row["employee_id"]}";
    }

    private DataRow? Selected => (grid.CurrentRow?.DataBoundItem as DataRowView)?.Row;

    private async void Loaded(object? sender, EventArgs e) => await RunAsync(() => ReadAsync());
    private async void RefreshClicked(object? sender, EventArgs e) => await RunAsync(() => ReadAsync());
    private void SelectionChanged(object sender, CurrentRowChangedEventArgs e) => UpdateActions();
    private void InputsChanged(object? sender, EventArgs e) => UpdateActions();

    private async Task ReadAsync(int? id = null)
    {
        var current = await repository!.ReadExperienceAsync(employee, lifetime.Token);
        revision = current.Revision;
        grid.DataSource = current.Rows.DefaultView;
        if (id.HasValue)
            grid.CurrentRow = grid.Rows.FirstOrDefault(row =>
                row.DataBoundItem is DataRowView item && item.Row.Field<int>("id") == id.Value);
        status.Text = current.Rows.Rows.Count == 0 ? "No experience records." : $"{current.Rows.Rows.Count:N0} experience records";
    }

    private void EditClicked(object? sender, EventArgs e)
    {
        if (Selected is not DataRow row)
            return;
        SetEditor(row);
    }

    private void NewClicked(object? sender, EventArgs e) => SetEditor(null);

    private void SetEditor(DataRow? row)
    {
        editing = row?.Field<int>("id");
        companyName.Text = row?.Field<string>("company_name") ?? "";
        designation.Text = row?.Field<string>("designation") ?? "";
        fromDate.Value = row?.Field<DateTime?>("from_date") ?? DateTime.Today;
        fromDate.Checked = row?.IsNull("from_date") == false;
        toDate.Value = row?.Field<DateTime?>("to_date") ?? DateTime.Today;
        toDate.Checked = row?.IsNull("to_date") == false;
        current.Checked = row?.Field<bool?>("is_current") == true;
        responsibilities.Text = row?.Field<string>("responsibilities") ?? "";
        save.Text = editing.HasValue ? "Save experience" : "Add experience";
    }

    private async void SaveClicked(object? sender, EventArgs e)
    {
        var draft = new EmployeeExperienceDraft(companyName.Text, designation.Text,
            fromDate.Checked ? fromDate.Value.Date : (DateTime?)null, toDate.Checked ? toDate.Value.Date : (DateTime?)null,
            current.Checked, responsibilities.Text);
        await RunAsync(async () =>
        {
            int id = await repository!.SaveExperienceAsync(employee, revision!, editing, draft, lifetime.Token);
            SetEditor(null);
            await ReadAsync(id);
        });
    }

    private void AskDelete(object? sender, EventArgs e)
    {
        if (Selected is not DataRow row)
            return;
        confirmationLabel.Text = $"Delete {row["company_name"]}?";
        confirmation.Visible = true;
        UpdateActions();
    }

    private void CancelDelete(object? sender, EventArgs e)
    {
        confirmation.Visible = false;
        UpdateActions();
    }

    private async void ConfirmDelete(object? sender, EventArgs e)
    {
        if (Selected is not DataRow row)
            return;
        confirmation.Visible = false;
        await RunAsync(async () =>
        {
            await repository!.SaveExperienceAsync(employee, revision!, row.Field<int>("id"), null, lifetime.Token);
            SetEditor(null);
            await ReadAsync();
        });
    }

    private async Task RunAsync(Func<Task> action)
    {
        if (repository is null || busy)
            return;
        busy = true;
        UpdateActions();
        status.Text = "Working with experience records…";
        try { await action(); }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or Npgsql.NpgsqlException or TimeoutException)
        {
            if (!lifetime.IsCancellationRequested)
                status.Text = error is InvalidOperationException or UnauthorizedAccessException
                    ? error.Message : "Could not update experience records. Check PostgreSQL and retry.";
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
        bool ready = !busy && !confirmation.Visible;
        bool canEdit = ready && writable && revision is not null;
        grid.Enabled = refresh.Enabled = ready;
        editor.Enabled = canEdit;
        save.Enabled = canEdit && !string.IsNullOrWhiteSpace(companyName.Text);
        newRecord.Enabled = canEdit;
        edit.Enabled = delete.Enabled = canEdit && Selected is not null;
        close.Enabled = !busy;
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

