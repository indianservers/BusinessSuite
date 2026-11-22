namespace Business_Suite;

internal sealed class BusinessComparisonWindow : Form
{
    public BusinessComparisonWindow(ComparisonResult result)
    {
        Text = "Business Suite | Compare business records";
        StartPosition = FormStartPosition.CenterParent;
        ClientSize = new Size(1020, 690);
        MinimumSize = new Size(820, 600);
        Font = new Font("Segoe UI", 10);

        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(18), RowCount = 4 };
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 54));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 60));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 40));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, result.Unavailable.Count == 0 ? 4 : 78));
        Controls.Add(layout);

        var introduction = new Label
        {
            Dock = DockStyle.Fill,
            Text = "Review possible matches among the records both accounts can access. This preview does not merge records."
        };
        layout.Controls.Add(introduction, 0, 0);

        var grid = new DataGridView
        {
            Dock = DockStyle.Fill, ReadOnly = true, AllowUserToAddRows = false, AllowUserToDeleteRows = false,
            MultiSelect = false, SelectionMode = DataGridViewSelectionMode.FullRowSelect, RowHeadersVisible = false,
            BackgroundColor = Color.White, AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill,
            AutoGenerateColumns = false,
            DataSource = result.Rows
        };
        grid.Columns.Add(new DataGridViewTextBoxColumn { DataPropertyName = nameof(ComparisonRow.Area), HeaderText = "Area" });
        grid.Columns.Add(new DataGridViewTextBoxColumn { DataPropertyName = nameof(ComparisonRow.Key), HeaderText = "Match key" });
        grid.Columns.Add(new DataGridViewTextBoxColumn { DataPropertyName = nameof(ComparisonRow.Status), HeaderText = "Comparison" });
        layout.Controls.Add(grid, 0, 1);

        var details = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 2 };
        details.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50));
        details.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50));
        details.RowStyles.Add(new RowStyle(SizeType.Absolute, 29));
        details.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        layout.Controls.Add(details, 0, 2);
        details.Controls.Add(new Label { Text = "Local record", Dock = DockStyle.Fill, TextAlign = ContentAlignment.BottomLeft }, 0, 0);
        details.Controls.Add(new Label { Text = "Server record", Dock = DockStyle.Fill, TextAlign = ContentAlignment.BottomLeft }, 1, 0);
        TextBox local = Preview("Local record");
        TextBox server = Preview("Server record");
        details.Controls.Add(local, 0, 1);
        details.Controls.Add(server, 1, 1);

        if (result.Unavailable.Count != 0)
        {
            TextBox errors = Preview("Areas unavailable for comparison");
            errors.Text = string.Join(Environment.NewLine, result.Unavailable);
            layout.Controls.Add(errors, 0, 3);
        }

        void PopulateDetails()
        {
            ComparisonRow? row = grid.CurrentRow?.DataBoundItem as ComparisonRow;
            local.Text = row?.Local ?? "";
            server.Text = row?.Server ?? "";
        }

        grid.SelectionChanged += (_, _) => PopulateDetails();
        Shown += (_, _) => PopulateDetails();
    }

    private static TextBox Preview(string label) => new()
    {
        Dock = DockStyle.Fill, ReadOnly = true, Multiline = true,
        ScrollBars = ScrollBars.Vertical, AccessibleName = label
    };
}
