using Npgsql;

namespace Business_Suite;

public partial class Settings : Form
{
    private CancellationTokenSource? connectionCheck;
    private DesktopDatabaseSettings? loadedSettings;
    private List<DesktopCompanyBranch> availableScopes = new();

    public Settings()
    {
        InitializeComponent();
    }

    private void Settings_Load(object? sender, EventArgs e)
    {
        environmentPath.Text = DesktopDatabaseSettings.EnvironmentPath;
    }

    private void Settings_FormClosed(object? sender, FormClosedEventArgs e)
    {
        connectionCheck?.Cancel();
    }

    private async void testButton_Click(object? sender, EventArgs e)
    {
        using var check = new CancellationTokenSource();
        connectionCheck = check;
        testButton.Enabled = false;
        applyScopeButton.Enabled = false;
        companySelector.Enabled = false;
        branchSelector.Enabled = false;
        loadedSettings = null;
        status.Text = "Checking PostgreSQL…";
        status.ForeColor = SystemColors.ControlText;
        try
        {
            var settings = DesktopDatabaseSettings.Load();
            using var connection = new NpgsqlConnection(settings.ConnectionString);
            await connection.OpenAsync(check.Token);
            var scopes = await settings.ListScopesAsync(connection, check.Token);
            if (!check.IsCancellationRequested)
            {
                if (scopes.Count == 0)
                    throw new UnauthorizedAccessException("The PostgreSQL login has no eligible company and branch.");
                loadedSettings = settings;
                availableScopes = scopes;
                companySelector.DataSource = scopes.GroupBy(scope => scope.CompanyId)
                    .Select(group => group.First()).ToList();
                companySelector.SelectedValue = settings.OrganizationId;
                if (companySelector.SelectedIndex == -1)
                    companySelector.SelectedIndex = 0;
                if (settings.BranchId is int branch)
                    branchSelector.SelectedValue = branch;
                if (branchSelector.SelectedIndex == -1 && branchSelector.Items.Count > 0)
                    branchSelector.SelectedIndex = 0;
                status.Text = "PostgreSQL verified. Choose a company and branch for this session.";
                status.ForeColor = Color.DarkGreen;
                companySelector.Enabled = true;
                branchSelector.Enabled = true;
                applyScopeButton.Enabled = branchSelector.SelectedIndex >= 0;
            }
        }
        catch (Exception error) when (error is NpgsqlException or IOException or UnauthorizedAccessException
            or ArgumentException or InvalidOperationException or TimeoutException or OperationCanceledException)
        {
            if (!check.IsCancellationRequested)
            {
                status.Text = error.GetBaseException() is System.Security.Authentication.AuthenticationException
                    ? "PostgreSQL certificate validation failed. Check the server name and Windows certificate trust."
                    : error is NpgsqlException or TimeoutException
                        ? "Could not verify PostgreSQL. Check the server, credentials and database schema."
                        : error.Message;
                status.ForeColor = Color.Firebrick;
            }
        }
        finally
        {
            connectionCheck = null;
            if (!IsDisposed)
                testButton.Enabled = true;
        }
    }

    private void companySelector_SelectedIndexChanged(object? sender, Telerik.WinControls.UI.Data.PositionChangedEventArgs e)
    {
        if (companySelector.SelectedItem?.DataBoundItem is not DesktopCompanyBranch company)
            return;
        branchSelector.DataSource = availableScopes.Where(scope => scope.CompanyId == company.CompanyId)
            .Select(scope => new ScopeBranch(scope.BranchId ?? 0, scope.Branch ?? "Company only")).ToList();
        applyScopeButton.Enabled = loadedSettings is not null && branchSelector.SelectedIndex >= 0;
    }

    private void applyScopeButton_Click(object? sender, EventArgs e)
    {
        if (loadedSettings is null || companySelector.SelectedItem?.DataBoundItem is not DesktopCompanyBranch company
            || branchSelector.SelectedItem?.DataBoundItem is not ScopeBranch branch)
            return;
        loadedSettings.ForScope(company.CompanyId, branch.Id == 0 ? null : branch.Id).SelectScope();
        status.ForeColor = Color.DarkGreen;
        status.Text = $"Working in {company.Company} / {branch.Name}.";
    }

    private sealed record ScopeBranch(int Id, string Name);
}
