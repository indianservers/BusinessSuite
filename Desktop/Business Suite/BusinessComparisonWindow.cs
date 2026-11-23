namespace Business_Suite;

internal sealed partial class BusinessComparisonWindow : Form
{
    public BusinessComparisonWindow()
    {
        InitializeComponent();
    }

    public BusinessComparisonWindow(ComparisonResult result) : this()
    {
        errors.Text = string.Join(Environment.NewLine, result.Unavailable);
        errors.Visible = result.Unavailable.Count != 0;
        grid.DataSource = result.Rows;
    }

    private void PopulateDetails(object sender, EventArgs e)
    {
        ComparisonRow? row = grid.CurrentRow?.DataBoundItem as ComparisonRow;
        local.Text = row?.Local ?? "";
        server.Text = row?.Server ?? "";
    }
}
