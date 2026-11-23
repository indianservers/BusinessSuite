using System.Data;
using Telerik.WinControls.UI;

namespace Business_Suite;

internal sealed partial class EmployeeSettlementRegisterForm : Form
{
    private readonly EmployeeAdministrationRepository? repository;
    private readonly CancellationTokenSource lifetime = new();
    private bool busy;

    public EmployeeSettlementRegisterForm() => InitializeComponent();

    internal EmployeeSettlementRegisterForm(DesktopDatabaseSettings settings) : this() =>
        repository = new EmployeeAdministrationRepository(settings);

    private DataRow? Selected => (grid.CurrentRow?.DataBoundItem as DataRowView)?.Row;
    private async void RegisterLoaded(object? sender,EventArgs e) => await ReloadAsync();
    private async void OwnStatementsChanged(object? sender,EventArgs e) => await ReloadAsync();
    private async void RefreshClicked(object? sender,EventArgs e) => await ReloadAsync();
    private void CloseClicked(object? sender,EventArgs e) => Close();
    private void SelectionChanged(object sender,CurrentRowChangedEventArgs e) => open.Enabled = !busy && Selected is not null;

    private async void OpenClicked(object? sender,EventArgs e)
    {
        if (repository is null || busy || Selected is not DataRow row)
            return;
        using var details = new EmployeeSettlementsForm(repository,row.Field<int>("employee"),row.Field<int?>("exit"),
            row.Field<string>("employee_name") ?? "",row.Field<int>("id"),ownStatements.Checked);
        details.ShowDialog(this);
        if (details.Changed)
            await ReloadAsync();
    }

    private async void PrepareClicked(object? sender,EventArgs e)
    {
        if (repository is null || busy || ownStatements.Checked)
            return;
        using var dialog = new EmployeeSettlementPreparationForm(repository);
        if (dialog.ShowDialog(this) == DialogResult.OK)
            await ReloadAsync();
    }

    private void TemplateClicked(object? sender,EventArgs e)
    {
        if (repository is null || busy || ownStatements.Checked)
            return;
        using var dialog = new EmployeeSettlementTemplateForm(repository);
        dialog.ShowDialog(this);
    }

    private async Task ReloadAsync()
    {
        if (repository is null || busy)
            return;
        busy = true;
        open.Enabled = refresh.Enabled = ownStatements.Enabled = false;
        prepare.Enabled = template.Enabled = false;
        message.Text = "Loading settlements…";
        grid.DataSource = null;
        try
        {
            var records = await repository.ReadSettlementRegisterAsync(search.Text,state.Text,lifetime.Token,ownStatements.Checked);
            if (IsDisposed)
                return;
            grid.DataSource = records.DefaultView;
            message.Text = records.Rows.Count == 0 ? "No settlements match this search." : $"{records.Rows.Count:N0} settlements";
        }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (UnauthorizedAccessException ex) { message.Text = ex.Message; }
        catch (InvalidOperationException ex) { message.Text = ex.Message; }
        catch (Npgsql.NpgsqlException) { message.Text = "PostgreSQL could not load settlements."; }
        finally
        {
            busy = false;
            if (!IsDisposed)
            {
                refresh.Enabled = ownStatements.Enabled = true;
                prepare.Enabled = template.Enabled = !ownStatements.Checked;
                open.Enabled = Selected is not null;
            }
        }
    }

    protected override void OnFormClosed(FormClosedEventArgs e)
    {
        lifetime.Cancel();
        base.OnFormClosed(e);
    }
}
