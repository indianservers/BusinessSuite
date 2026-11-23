using Npgsql;
using System.Text;

namespace Business_Suite;

public sealed partial class EmployeeDirectoryForm : Form
{
    private readonly EmployeeDirectoryRepository? repository;
    private readonly DesktopDatabaseSettings? settings;
    private readonly CancellationTokenSource lifetime = new();
    private string appliedSearch = "";
    private string appliedSkill = "";
    private bool appliedTeamOnly;
    private int pageIndex;
    private long matchingEmployees;

    public EmployeeDirectoryForm()
    {
        InitializeComponent();
    }

    internal EmployeeDirectoryForm(DesktopDatabaseSettings settings) : this()
    {
        this.settings = settings;
        repository = new EmployeeDirectoryRepository(settings);
    }

    private async void EmployeeDirectoryForm_Load(object? sender, EventArgs e) => await ReloadAsync();
    private async void searchButton_Click(object? sender, EventArgs e) => await ReloadAsync();
    private async void previousButton_Click(object? sender, EventArgs e) => await ReloadAsync(pageIndex - 1);
    private async void nextButton_Click(object? sender, EventArgs e) => await ReloadAsync(pageIndex + 1);
    private void EmployeeDirectoryForm_FormClosed(object? sender, FormClosedEventArgs e) => lifetime.Cancel();

    private void settlementRegisterButton_Click(object? sender,EventArgs e)
    {
        if (settings is null)
            return;
        using var register = new EmployeeSettlementRegisterForm(settings);
        register.ShowDialog(this);
    }

    private void myProfileRequestButton_Click(object? sender, EventArgs e)
    {
        if (settings is null)
            return;
        using var requests = new EmployeeMyProfileRequestsForm(settings);
        requests.ShowDialog(this);
    }

    private async void administrationButton_Click(object? sender, EventArgs e)
    {
        if (settings is null)
            return;
        using var administration = new EmployeeAdministrationForm(settings);
        administration.ShowDialog(this);
        await ReloadAsync();
    }

    private async Task ReloadAsync(int? requestedPage = null)
    {
        if (repository is null || !searchButton.Enabled)
            return;

        searchButton.Enabled = false;
        exportButton.Enabled = false;
        previousButton.Enabled = nextButton.Enabled = false;
        statusLabel.Text = "Loading employees…";
        try
        {
            string search = requestedPage.HasValue ? appliedSearch : searchBox.Text;
            string skill = requestedPage.HasValue ? appliedSkill : skillBox.Text;
            bool teamOnly = requestedPage.HasValue ? appliedTeamOnly : teamOnlyBox.Checked;
            int page = Math.Max(0, requestedPage ?? 0);
            var result = await repository.ListPageAsync(search, skill, teamOnly, page, lifetime.Token);
            if (page > 0 && result.Employees.Rows.Count == 0)
            {
                page = 0;
                result = await repository.ListPageAsync(search, skill, teamOnly, page, lifetime.Token);
            }
            if (!lifetime.IsCancellationRequested)
            {
                var table = result.Employees;
                employeeGrid.DataSource = table;
                appliedSearch = search;
                appliedSkill = skill;
                appliedTeamOnly = teamOnly;
                pageIndex = page;
                matchingEmployees = result.Total;
                UpdateNavigation();
                long first = (long)pageIndex * EmployeeDirectoryRepository.PageSize + 1;
                statusLabel.Text = matchingEmployees switch
                {
                    0 => "No employees match the search.",
                    1 => "1 employee",
                    _ => $"Showing {first:N0}–{first + table.Rows.Count - 1:N0} of {matchingEmployees:N0} employees"
                };
            }
        }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or InvalidOperationException or UnauthorizedAccessException)
        {
            if (!lifetime.IsCancellationRequested)
            {
                employeeGrid.DataSource = null;
                matchingEmployees = 0;
                statusLabel.Text = error is InvalidOperationException or UnauthorizedAccessException
                    ? error.Message : "Could not load the directory from PostgreSQL.";
            }
        }
        finally
        {
            if (!lifetime.IsCancellationRequested)
                searchButton.Enabled = true;
        }
    }

    private async void exportButton_Click(object? sender, EventArgs e)
    {
        if (repository is null || exportDialog.ShowDialog(this) != DialogResult.OK)
            return;

        exportButton.Enabled = false;
        searchButton.Enabled = false;
        previousButton.Enabled = nextButton.Enabled = false;
        statusLabel.Text = "Exporting employee directory…";
        try
        {
            var data = await repository.ListFilteredAsync(appliedSearch, appliedSkill, appliedTeamOnly,
                lifetime.Token, export: true);
            if (lifetime.IsCancellationRequested)
                return;
            using var file = new StreamWriter(exportDialog.FileName, false, new UTF8Encoding(true));
            file.WriteLine("Employee ID,Name,Department,Designation,Branch,Work location,Status,Email,Phone");
            foreach (System.Data.DataRow row in data.Rows)
                file.WriteLine(string.Join(",", row.ItemArray.Select(value =>
                    CrmDirectoryForm.CsvCell(Convert.ToString(value) ?? ""))));
            statusLabel.Text = $"Exported {data.Rows.Count:N0} employee records.";
        }
        catch (OperationCanceledException) when (lifetime.IsCancellationRequested) { }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException or NpgsqlException
            or InvalidOperationException or TimeoutException)
        {
            if (!lifetime.IsCancellationRequested)
                statusLabel.Text = "Could not export the directory. Check the database and file destination.";
        }
        finally
        {
            if (!lifetime.IsCancellationRequested)
            {
                searchButton.Enabled = true;
                UpdateNavigation();
            }
        }
    }

    private void UpdateNavigation()
    {
        exportButton.Enabled = matchingEmployees > 0;
        previousButton.Enabled = pageIndex > 0 && matchingEmployees > 0;
        nextButton.Enabled = ((long)pageIndex + 1) * EmployeeDirectoryRepository.PageSize < matchingEmployees;
    }
}
