using Telerik.WinControls.UI;

namespace Business_Suite;

public sealed partial class MainForm : Form
{
    public MainForm()
    {
        InitializeComponent();
    }

    private void workspaces_SelectedIndexChanged(object? sender, EventArgs e)
    {
        var page = workspaces.SelectedTab;
        if (page == homePage)
        {
            if (GetModuleWorkspace(ribbonBar.SelectedCommandTab) != null)
                homeTab.IsSelected = true;
            return;
        }

        foreach (RibbonTab tab in ribbonBar.CommandTabs)
        {
            if (page != null && GetModuleWorkspace(tab) == page)
            {
                tab.IsSelected = true;
                return;
            }
        }
    }

    private void ribbonBar_CommandTabSelected(object? sender, CommandTabEventArgs e)
    {
        workspaces.SelectedTab = GetModuleWorkspace(e.CommandTab) ?? homePage;
    }

    private TabPage? GetModuleWorkspace(RibbonTab? tab) => tab switch
    {
        var selected when selected == appointmentsTab => appointmentsPage,
        var selected when selected == crmTab => crmPage,
        var selected when selected == financeTab => financePage,
        var selected when selected == hrmsTab => hrmsPage,
        var selected when selected == projectsTab => projectsPage,
        var selected when selected == salesTab => salesPage,
        _ => null
    };

    private void appointmentsButton_Click(object? sender, EventArgs e) => appointmentsTab.IsSelected = true;
    private void crmButton_Click(object? sender, EventArgs e) => crmTab.IsSelected = true;
    private void financeButton_Click(object? sender, EventArgs e) => financeTab.IsSelected = true;
    private void hrmsButton_Click(object? sender, EventArgs e) => hrmsTab.IsSelected = true;
    private void projectsButton_Click(object? sender, EventArgs e) => projectsTab.IsSelected = true;
    private void salesButton_Click(object? sender, EventArgs e) => salesTab.IsSelected = true;
    private void dataButton_Click(object? sender, EventArgs e) => Open(new BusinessDataForm());
    private void administrationButton_Click(object? sender, EventArgs e) => Open(new CompanyAdministrationForm());
    private void documentsButton_Click(object? sender, EventArgs e) =>
        OpenDatabaseWorkspace(settings => new DocumentsAndCommunicationForm(settings));
    private void powerButton_Click(object? sender, EventArgs e) => Open(new PowerAppsForm());
    private void reportingButton_Click(object? sender, EventArgs e) => Open(new ReportingAndCustomizationForm());
    private void localCompaniesButton_Click(object? sender, EventArgs e) => Open(new CompaniesGridForm());
    private void homeButton_Click(object? sender, EventArgs e) => workspaces.SelectedTab = homePage;
    private void settingsButton_Click(object? sender, EventArgs e) => Open(new Settings());
    private void helpButton_Click(object? sender, EventArgs e) => ShowNavigationHelp();
    private void crmWorkspaceButton_Click(object? sender, EventArgs e) => Open(new CrmForm());
    private void companiesButton_Click(object? sender, EventArgs e) => OpenCompanies();
    private void contactsButton_Click(object? sender, EventArgs e) => OpenContacts();
    private void leadsButton_Click(object? sender, EventArgs e) => OpenLeads();
    private void dealsButton_Click(object? sender, EventArgs e) => OpenDeals();

    private void appointmentSchedulerButton_Click(object? sender, EventArgs e) =>
        OpenDatabaseWorkspace(settings => new AppointmentsForm(settings));
    private void financeWorkspaceButton_Click(object? sender, EventArgs e) => Open(new FinanceAndAccountingForm());
    private void financeLedgersButton_Click(object? sender, EventArgs e) => Open(new FinanceAndAccountingForm());
    private void financeWorkspacesButton_Click(object? sender, EventArgs e) => Open(new FinanceAndAccountingForm());
    private void hrWorkspaceButton_Click(object? sender, EventArgs e) =>
        OpenDatabaseWorkspace(settings => new EmployeeDirectoryForm(settings));
    private void hrWorkspacesButton_Click(object? sender, EventArgs e) => Open(new HrmsForm());
    private void projectWorkspaceButton_Click(object? sender, EventArgs e) =>
        OpenDatabaseWorkspace(settings => new ProjectManagementForm(settings));
    private void projectWorkspacesButton_Click(object? sender, EventArgs e) =>
        OpenDatabaseWorkspace(settings => new PmsWorkspacesForm(settings));
    private void projectMyWorkButton_Click(object? sender, EventArgs e) =>
        OpenDatabaseWorkspace(settings => new PmsMyWorkForm(settings));
    private void salesWorkspaceButton_Click(object? sender, EventArgs e) =>
        OpenDatabaseWorkspace(settings => new SalesAndPosForm(settings));
    private void salesAppointmentsButton_Click(object? sender, EventArgs e) =>
        OpenDatabaseWorkspace(settings => new AppointmentsForm(settings));
    private void OpenCompanies() => Open(new CrmDirectoryForm(CrmDirectoryKind.Companies));
    private void OpenContacts() => Open(new CrmDirectoryForm(CrmDirectoryKind.Contacts));
    private void OpenLeads() => Open(new LeadsForm());
    private void OpenDeals() => OpenDatabaseWorkspace(settings => new CrmDealsForm(settings));

    private void OpenDatabaseWorkspace(Func<DesktopDatabaseSettings, Form> create)
    {
        try
        {
            Open(create(DesktopDatabaseSettings.Load()));
        }
        catch (Exception error) when (error is ArgumentException or IOException or UnauthorizedAccessException
            or InvalidOperationException)
        {
            MessageBox.Show(this, error.Message, "Business Suite", MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }
    }

    private void ShowNavigationHelp() => MessageBox.Show(this,
        "Select a module tab on the ribbon to see its commands. Select Home for the launcher.",
        "Business Suite Help", MessageBoxButtons.OK, MessageBoxIcon.Information);

    private void Open(Form form)
    {
        using (form)
            form.ShowDialog(this);
    }
}
