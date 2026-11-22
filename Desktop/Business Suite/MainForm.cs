namespace Business_Suite;

public sealed class MainForm : Form
{
    public MainForm()
    {
        Text = "Business Suite";
        StartPosition = FormStartPosition.CenterScreen;
        ClientSize = new Size(860, 490);
        MinimumSize = new Size(740, 460);
        Font = new Font("Segoe UI", 10);
        BackColor = Color.FromArgb(243, 246, 251);

        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(26), ColumnCount = 2, RowCount = 2 };
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50));
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 68));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        var heading = new Label { Text = "Business Suite", Dock = DockStyle.Fill, Font = new Font("Segoe UI Semibold", 28) };
        layout.Controls.Add(heading, 0, 0);
        layout.SetColumnSpan(heading, 2);

        var modules = CreateGroup("Modules");
        var shared = CreateGroup("Shared");
        layout.Controls.Add(modules, 0, 1);
        layout.Controls.Add(shared, 1, 1);
        AddForm(modules, "AI HRMS", () => new HrmsForm());
        AddForm(modules, "VyaparaCRM", () => new CrmForm());
        AddForm(modules, "KaryaFlow PMS", () => new ProjectManagementForm());
        AddForm(modules, "Sales & POS", () => new SalesAndPosForm());
        AddForm(modules, "Finance & Accounting", () => new FinanceAndAccountingForm());
        AddForm(modules, "Appointments", () => new AppointmentsForm());
        AddForm(shared, "Company administration", () => new CompanyAdministrationForm());
        AddForm(shared, "Shared business data", () => new BusinessDataForm());
        AddForm(shared, "Power Apps", () => new PowerAppsForm());
        AddForm(shared, "Documents & communication", () => new DocumentsAndCommunicationForm());
        AddForm(shared, "Reporting & customization", () => new ReportingAndCustomizationForm());
        AddForm(shared, "Desktop connection settings", () => new Settings());
        AddForm(shared, "Local companies", () => new CompaniesGridForm());
        Controls.Add(layout);
    }

    private static FlowLayoutPanel CreateGroup(string title)
    {
        var panel = new FlowLayoutPanel { Dock = DockStyle.Fill, FlowDirection = FlowDirection.TopDown,
            WrapContents = false, AutoScroll = true };
        panel.Controls.Add(new Label { Text = title, AutoSize = true, Font = new Font("Segoe UI Semibold", 14) });
        return panel;
    }

    private void AddForm(FlowLayoutPanel parent, string label, Func<Form> create)
    {
        var button = new Button { Text = label, Size = new Size(284, 43), TextAlign = ContentAlignment.MiddleLeft,
            Padding = new Padding(10, 0, 0, 0), FlatStyle = FlatStyle.Flat, BackColor = Color.White };
        button.FlatAppearance.BorderColor = Color.FromArgb(210, 221, 237);
        button.Click += (_, _) =>
        {
            using Form form = create();
            form.ShowDialog(this);
        };
        parent.Controls.Add(button);
    }
}
