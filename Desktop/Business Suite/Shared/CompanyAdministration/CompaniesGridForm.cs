using System.Data;
using Npgsql;

namespace Business_Suite;

public sealed partial class CompaniesGridForm : Form
{
    private readonly CancellationTokenSource lifetime = new();

    public CompaniesGridForm()
    {
        InitializeComponent();
    }

    private async void LoadCompanies(object sender, EventArgs e) => await LoadCompaniesAsync();

    private void CancelLoad(object sender, FormClosedEventArgs e) => lifetime.Cancel();

    private async Task LoadCompaniesAsync()
    {
        CancellationToken cancellation = lifetime.Token;
        refresh.Enabled = false;
        status.Text = "Loading companies…";
        try
        {
            var settings = DesktopDatabaseSettings.Load();

            await using var connection = new NpgsqlConnection(settings.ConnectionString);
            await connection.OpenAsync(cancellation);
            using var transaction = connection.BeginTransaction(IsolationLevel.RepeatableRead);
            await settings.RequireActorAsync(connection, transaction, cancellation);
            using var command = new NpgsqlCommand(
                "SELECT id, name, is_active FROM public.companies WHERE id=@company AND is_active",
                connection, transaction);
            command.Parameters.AddWithValue("company", settings.OrganizationId);
            await using var reader = await command.ExecuteReaderAsync(cancellation);
            var table = new DataTable();
            table.Columns.Add("id", typeof(int));
            table.Columns.Add("name", typeof(string));
            table.Columns.Add("is_active", typeof(bool));
            while (await reader.ReadAsync(cancellation))
                table.Rows.Add(reader.GetInt32(0), reader.GetString(1), reader.GetBoolean(2));
            if (IsDisposed || cancellation.IsCancellationRequested)
                return;
            grid.DataSource = table;
            status.Text = table.Rows.Count == 0 ? "No active company is available." : "Configured company";
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or ArgumentException
            or IOException or UnauthorizedAccessException or InvalidOperationException)
        {
            if (!IsDisposed)
                status.Text = error is UnauthorizedAccessException or InvalidOperationException or ArgumentException
                    ? error.Message : "Could not load the company. Check PostgreSQL and the desktop environment file.";
        }
        finally
        {
            if (!IsDisposed)
                refresh.Enabled = true;
        }
    }
}
