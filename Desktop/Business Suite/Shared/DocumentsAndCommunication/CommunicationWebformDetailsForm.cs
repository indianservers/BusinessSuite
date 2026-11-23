namespace Business_Suite;

public partial class CommunicationWebformDetailsForm : Form
{
    public CommunicationWebformDetailsForm() => InitializeComponent();

    internal CommunicationWebformDetailsForm(WebformDetail detail) : this()
    {
        headerLabel.Text = detail.Name;
        string status = detail.Active ? "Active" : "Inactive";
        string rule = detail.Rule is int id ? $"Rule #{id}" : "No automatic response";
        summaryLabel.Text = $"{detail.Slug}  |  CRM target: {detail.Target}{Environment.NewLine}{status}  |  {rule}";
        fieldsGrid.DataSource = detail.Fields;
        statusLabel.Text = detail.Fields.Count == 0 ? "No customer fields or CRM mappings are configured." : "";
    }
}
