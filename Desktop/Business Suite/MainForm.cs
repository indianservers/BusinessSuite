using System;
using System.Windows.Forms;

namespace Business_Suite
{
    public sealed partial class MainForm : Form
    {
        public MainForm()
        {
            InitializeComponent();
        }

        private void appointmentsButton_Click(object sender, EventArgs e)
        {
            using (var form = new AppointmentsForm())
                form.ShowDialog(this);
        }

        private void crmButton_Click(object sender, EventArgs e)
        {
            using (var form = new CrmForm())
                form.ShowDialog(this);
        }

        private void financeAndAccountingButton_Click(object sender, EventArgs e)
        {
            using (var form = new FinanceAndAccountingForm())
                form.ShowDialog(this);
        }

        private void hrmsButton_Click(object sender, EventArgs e)
        {
            using (var form = new HrmsForm())
                form.ShowDialog(this);
        }

        private void projectManagementButton_Click(object sender, EventArgs e)
        {
            using (var form = new ProjectManagementForm())
                form.ShowDialog(this);
        }

        private void salesAndPosButton_Click(object sender, EventArgs e)
        {
            using (var form = new SalesAndPosForm())
                form.ShowDialog(this);
        }

        private void businessDataButton_Click(object sender, EventArgs e)
        {
            using (var form = new BusinessDataForm())
                form.ShowDialog(this);
        }

        private void companyAdministrationButton_Click(object sender, EventArgs e)
        {
            using (var form = new CompanyAdministrationForm())
                form.ShowDialog(this);
        }

        private void documentsAndCommunicationButton_Click(object sender, EventArgs e)
        {
            using (var form = new DocumentsAndCommunicationForm())
                form.ShowDialog(this);
        }

        private void powerAppsButton_Click(object sender, EventArgs e)
        {
            using (var form = new PowerAppsForm())
                form.ShowDialog(this);
        }

        private void reportingAndCustomizationButton_Click(object sender, EventArgs e)
        {
            using (var form = new ReportingAndCustomizationForm())
                form.ShowDialog(this);
        }

        private void settingsButton_Click(object sender, EventArgs e)
        {
            using (var form = new Settings())
                form.ShowDialog(this);
        }

        private void companiesGridButton_Click(object sender, EventArgs e)
        {
            using (var form = new CompaniesGridForm())
                form.ShowDialog(this);
        }
    }
}
