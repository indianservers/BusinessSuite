using System.Data;
using Telerik.WinControls.UI;

namespace Business_Suite;

internal sealed partial class EmployeeOnboardingForm : Form
{
    private readonly EmployeeAdministrationRepository? repository;
    private readonly int employee;
    private readonly CancellationTokenSource lifetime = new();
    private bool writable;
    private bool busy;

    public EmployeeOnboardingForm() => InitializeComponent();

    internal EmployeeOnboardingForm(EmployeeAdministrationRepository repository, int employee, string label) : this()
    {
        this.repository = repository;
        this.employee = employee;
        heading.Text = label;
    }

    internal bool Changed { get; private set; }
    private DataRow? Selected => (grid.CurrentRow?.DataBoundItem as DataRowView)?.Row;

    private async void OnboardingLoaded(object? sender, EventArgs e) => await RunAsync(ReadAsync);
    private async void RefreshClicked(object? sender, EventArgs e) => await RunAsync(ReadAsync);
    private void SelectionChanged(object sender, CurrentRowChangedEventArgs e) => UpdateActions();
    private void InputsChanged(object? sender, EventArgs e) => UpdateActions();

    private async Task ReadAsync()
    {
        var result = await repository!.ReadOnboardingAsync(employee, lifetime.Token);
        writable = result.CanWrite;
        template.DisplayMember = "name";
        template.ValueMember = "id";
        template.DataSource = result.Templates;
        template.SelectedIndex = -1;
        grid.DataSource = result.Tasks.DefaultView;
        progress.Text = result.Progress ?? "No onboarding plan.";
        status.Text = result.Tasks.Rows.Count == 0 ? "No onboarding tasks." : $"{result.Tasks.Rows.Count:N0} onboarding tasks";
    }

    private async void ApplyTemplateClicked(object? sender, EventArgs e)
    {
        if (template.SelectedValue is not int id || !assign.Enabled)
            return;
        await RunAsync(async () =>
        {
            await repository!.ApplyOnboardingTemplateAsync(employee, id, lifetime.Token);
            Changed = true;
            await ReadAsync();
        });
    }

    private async void CompleteClicked(object? sender, EventArgs e)
    {
        if (Selected is not DataRow row || !complete.Enabled)
            return;
        await RunAsync(async () =>
        {
            await repository!.CompleteOnboardingTaskAsync(employee, row.Field<int>("id"), row.Field<string>("revision")!,
                reason.Text, lifetime.Token);
            Changed = true;
            reason.Clear();
            await ReadAsync();
        });
    }

    private async Task RunAsync(Func<Task> work)
    {
        if (repository is null || busy)
            return;
        busy = true;
        UpdateActions();
        status.Text = "Working with onboarding records…";
        try { await work(); }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is InvalidOperationException or UnauthorizedAccessException
            or Npgsql.NpgsqlException or TimeoutException)
        {
            if (!lifetime.IsCancellationRequested)
                status.Text = error is InvalidOperationException or UnauthorizedAccessException ? error.Message
                    : "Could not update onboarding. Check PostgreSQL and refresh.";
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
        grid.Enabled = refresh.Enabled = close.Enabled = !busy;
        template.Enabled = !busy && writable;
        assign.Enabled = template.Enabled && template.SelectedValue is int;
        reason.Enabled = template.Enabled && Selected?.Field<bool>("open") == true;
        complete.Enabled = reason.Enabled && reason.Text.Trim().Length >= 3;
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
