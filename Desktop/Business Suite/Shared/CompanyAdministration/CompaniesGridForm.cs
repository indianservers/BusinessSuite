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
            string? configured = Environment.GetEnvironmentVariable("BUSINESS_SUITE_POSTGRES");
            var settings = new NpgsqlConnectionStringBuilder(configured ??
                "Host=127.0.0.1;Port=5432;Database=business_suite;Username=business_suite");
            if (!string.Equals(settings.Host, "localhost", StringComparison.OrdinalIgnoreCase)
                && settings.Host != "127.0.0.1" && settings.Host != "::1")
                throw new ArgumentException("A loopback PostgreSQL address is required.");

            await using var connection = new NpgsqlConnection(settings.ConnectionString);
            await connection.OpenAsync(cancellation);
            using var command = new NpgsqlCommand(
                "SELECT id, name, COALESCE(is_active, false) AS is_active FROM public.companies ORDER BY id LIMIT 500",
                connection);
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
            status.Text = table.Rows.Count == 500 ? "Showing the first 500 companies" : $"{table.Rows.Count} companies loaded";
        }
        catch (OperationCanceledException) when (cancellation.IsCancellationRequested) { }
        catch (Exception error) when (error is NpgsqlException or TimeoutException or ArgumentException)
        {
            if (!IsDisposed)
                status.Text = "Could not load companies. Check local PostgreSQL and BUSINESS_SUITE_POSTGRES.";
        }
        finally
        {
            if (!IsDisposed)
                refresh.Enabled = true;
        }
    }
}
