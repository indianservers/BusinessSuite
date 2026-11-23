using System.Data;

namespace Business_Suite;

public sealed partial class CrmRecordForm : Form
{
    public CrmRecordForm()
    {
        InitializeComponent();
    }

    internal CrmRecordForm(DataRowView record, CrmDirectoryKind kind) : this()
    {
        bool company = kind == CrmDirectoryKind.Companies;
        headingLabel.Text = Value("name");
        detailsBox.Text = string.Join(Environment.NewLine, new[]
        {
            Line("Record ID", "id"),
            Line(company ? "Legal name" : "Job title", "detail_name"),
            Line(company ? "Relationship" : "Lifecycle stage", "classification"),
            Line(company ? "Industry" : "Company", "context"),
            Line("Email", "email"),
            Line("Phone", "phone_display"),
            Line("Website", "website"),
            Line("Address", "address"),
            Line("City", "city"),
            Line("State", "state"),
            Line("Country", "country"),
            Line("Status", "status"),
            Line("Tags", "tags")
        });

        string Line(string label, string field) => $"{label}: {Value(field)}";
        string Value(string field) => record[field] is DBNull ? "" : Convert.ToString(record[field]) ?? "";
    }
}
