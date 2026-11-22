using System.Data;
using Npgsql;
using Telerik.WinControls.UI;

namespace Business_Suite;

public sealed class CompaniesGridForm : Form
{
    private readonly RadGridView grid = new();
    private readonly Label status = new();
    private readonly Button refresh = new();
    private readonly CancellationTokenSource lifetime = new();

    public CompaniesGridForm()
    {
        Text = "Business Suite | Local companies";
        StartPosition = FormStartPosition.CenterParent;
        ClientSize = new Size(920, 530);
        MinimumSize = new Size(640, 390);
        BackColor = Color.FromArgb(243, 246, 251);
        ForeColor = Color.FromArgb(24, 35, 58);
        Font = new Font("Segoe UI", 10);

        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(27), ColumnCount = 1, RowCount = 4 };
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 50));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 43));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 45));
        layout.Controls.Add(new Label { Text = "Local companies", Dock = DockStyle.Fill,
            Font = new Font("Segoe UI Semibold", 27) }, 0, 0);
        layout.Controls.Add(new Label { Text = "Company records from Business Suite · PostgreSQL",
            Dock = DockStyle.Fill, ForeColor = Color.FromArgb(84, 100, 124) }, 0, 1);

        grid.Dock = DockStyle.Fill;
        grid.ReadOnly = true;
        grid.ShowGroupPanel = false;
        grid.AllowAddNewRow = false;
        grid.AllowDeleteRow = false;
        grid.AutoGenerateColumns = false;
        grid.AutoSizeColumnsMode = GridViewAutoSizeColumnsMode.Fill;
        grid.EnableFiltering = true;
        grid.Columns.Add(new GridViewTextBoxColumn("id") { HeaderText = "Company ID", Width = 110 });
        grid.Columns.Add(new GridViewTextBoxColumn("name") { HeaderText = "Company name", Width = 570 });
        grid.Columns.Add(new GridViewCheckBoxColumn("is_active") { HeaderText = "Active", Width = 100 });
        layout.Controls.Add(grid, 0, 2);

        var footer = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2 };
        footer.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        footer.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 104));
        status.Dock = DockStyle.Fill;
        status.TextAlign = ContentAlignment.MiddleLeft;
        refresh.Text = "Refresh";
        refresh.Dock = DockStyle.Fill;
        footer.Controls.Add(status, 0, 0);
        footer.Controls.Add(refresh, 1, 0);
        layout.Controls.Add(footer, 0, 3);
        Controls.Add(layout);

        Shown += async (_, _) => await LoadCompaniesAsync();
        refresh.Click += async (_, _) => await LoadCompaniesAsync();
        FormClosed += (_, _) => lifetime.Cancel();
    }

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
