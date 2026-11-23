using System.Data;
using Telerik.WinControls.UI;

namespace Business_Suite;

internal sealed partial class EmployeeQuickAddForm : Form
{
    private readonly EmployeeAdministrationRepository? repository;
    private readonly CancellationTokenSource lifetime = new();
    private bool saving;

    public EmployeeQuickAddForm() => InitializeComponent();

    internal EmployeeQuickAddForm(EmployeeAdministrationRepository repository) : this() => this.repository = repository;

    internal int EmployeeId { get; private set; }

    private async void QuickAddLoaded(object? sender, EventArgs e)
    {
        if (repository is null)
            return;
        status.Text = "Loading departments…";
        try
        {
            var departments = await repository.ReadCreateDepartmentsAsync(lifetime.Token);
            if (lifetime.IsCancellationRequested)
                return;
            department.Items.Add(new RadListDataItem("Unassigned"));
            foreach (DataRow row in departments.Rows)
                department.Items.Add(new RadListDataItem(row.Field<string>("name")) { Value = row.Field<int>("id") });
            department.SelectedIndex = 0;
            editor.Enabled = true;
            status.Text = "The employee will be added to the selected branch.";
            UpdateActions();
        }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or Npgsql.NpgsqlException or TimeoutException)
        {
            if (!lifetime.IsCancellationRequested)
                status.Text = error is InvalidOperationException or UnauthorizedAccessException ? error.Message
                    : "Could not load departments from PostgreSQL.";
        }
    }

    private void InputChanged(object? sender, EventArgs e) => UpdateActions();

    private void UpdateActions()
    {
        add.Enabled = editor.Enabled && !saving && !string.IsNullOrWhiteSpace(firstName.Text);
        close.Enabled = !saving;
    }

    private async void AddClicked(object? sender, EventArgs e)
    {
        if (repository is null || !add.Enabled)
            return;
        saving = true;
        UpdateActions();
        status.Text = "Creating employee…";
        try
        {
            var draft = new EmployeeQuickAddDraft(firstName.Text, lastName.Text, joining.Value.Date,
                department.SelectedItem?.Value is int id ? id : (int?)null, email.Text, employmentType.Text);
            var created = await repository.QuickAddAsync(draft, lifetime.Token);
            EmployeeId = created.Id;
        }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or Npgsql.NpgsqlException or TimeoutException)
        {
            status.Text = error is InvalidOperationException or UnauthorizedAccessException ? error.Message
                : "Could not add the employee. Check PostgreSQL and retry.";
        }
        finally
        {
            saving = false;
            UpdateActions();
        }
        if (EmployeeId > 0)
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
