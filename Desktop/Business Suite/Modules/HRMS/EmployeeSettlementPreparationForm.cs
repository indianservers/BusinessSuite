using System.Data;

namespace Business_Suite;

internal sealed partial class EmployeeSettlementPreparationForm : Form
{
    private readonly EmployeeAdministrationRepository? repository;
    private readonly CancellationTokenSource lifetime = new();
    private DataTable? exits;
    private bool busy;

    public EmployeeSettlementPreparationForm() => InitializeComponent();

    internal EmployeeSettlementPreparationForm(EmployeeAdministrationRepository repository) : this() =>
        this.repository = repository;

    private async void PreparationLoaded(object? sender, EventArgs e) => await FindAsync();
    private async void LoadClicked(object? sender, EventArgs e) => await FindAsync();
    private void CloseClicked(object? sender, EventArgs e) => Close();
    private async void EmployeeChanged(object? sender, Telerik.WinControls.UI.Data.PositionChangedEventArgs e)
    {
        if (busy || employee.SelectedValue is not int id)
            return;
        await RunAsync(async () =>
        {
            exits = null;
            exitList.DataSource = null;
            var options = await repository!.ReadSettlementPreparationExitsAsync(id,lifetime.Token);
            var current = options.Rows.Count > 0 ? options.Rows[0] : null;
            var fallback = options.NewRow();
            fallback["id"] = 0;
            fallback["label"] = "Use current exit or create one";
            fallback["last_working_date"] = current?["last_working_date"] ?? DBNull.Value;
            fallback["status"] = current?["status"] ?? DBNull.Value;
            options.Rows.InsertAt(fallback,0);
            exits = options;
            exitList.DisplayMember = "label";
            exitList.ValueMember = "id";
            exitList.DataSource = options.DefaultView;
            exitList.SelectedIndex = 0;
            UpdateExitDate();
        });
    }

    private void ExitChanged(object? sender, Telerik.WinControls.UI.Data.PositionChangedEventArgs e)
    {
        if (!busy)
            UpdateExitDate();
    }

    private DataRow? SelectedExit => exitList.SelectedValue is int id
        ? exits?.Rows.Cast<DataRow>().FirstOrDefault(row => row.Field<int>("id") == id) : null;

    private void UpdateExitDate()
    {
        lastDay.Value = SelectedExit?.Field<DateTime?>("last_working_date") ?? DateTime.Today;
        reason.Clear();
        UpdateActions();
    }

    private Task FindAsync() => RunAsync(async () =>
    {
        var candidates = await repository!.ReadSettlementCandidatesAsync(search.Text,lifetime.Token);
        exits = null;
        exitList.DataSource = null;
        employee.DisplayMember = "label";
        employee.ValueMember = "id";
        employee.DataSource = candidates.DefaultView;
        employee.SelectedIndex = -1;
        message.Text = candidates.Rows.Count == 0 ? "No employees match this search." : "Choose an employee and confirm the last working date.";
    });

    private async void GenerateClicked(object? sender, EventArgs e)
    {
        if (!generate.Enabled || employee.SelectedValue is not int id || SelectedExit is not DataRow selected)
            return;
        await RunAsync(async () =>
        {
            int exit = selected.Field<int>("id");
            var created = await repository!.PrepareStandaloneSettlementAsync(id,lastDay.Value.Date,reason.Text,remarks.Text,
                lifetime.Token,exit == 0 ? null : (int?)exit);
            using var detail = new EmployeeSettlementsForm(repository,id,created.Exit,employee.Text,created.Settlement);
            detail.ShowDialog(this);
            DialogResult = DialogResult.OK;
        });
    }

    private async Task RunAsync(Func<Task> action)
    {
        if (repository is null || busy)
            return;
        busy = true;
        UpdateActions();
        try { await action(); }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (UnauthorizedAccessException ex) { message.Text = ex.Message; }
        catch (InvalidOperationException ex) { message.Text = ex.Message; }
        catch (Npgsql.NpgsqlException) { message.Text = "PostgreSQL could not prepare the settlement."; }
        finally
        {
            busy = false;
            if (!IsDisposed)
                UpdateActions();
        }
    }

    private void UpdateActions()
    {
        load.Enabled = search.Enabled = employee.Enabled = remarks.Enabled = close.Enabled = !busy;
        exitList.Enabled = !busy && exits is not null;
        var selected = SelectedExit;
        bool closed = selected?.Field<string>("status") is "Completed" or "Cancelled";
        lastDay.Enabled = reason.Enabled = !busy && selected is not null && !closed;
        generate.Enabled = !busy && employee.SelectedValue is int && selected is not null;
    }

    protected override void OnFormClosed(FormClosedEventArgs e)
    {
        lifetime.Cancel();
        base.OnFormClosed(e);
    }
}
