using System;
using System.Windows.Forms;

namespace Business_Suite
{
    public sealed partial class CrmForm : Form
    {
        public CrmForm()
        {
            InitializeComponent();
        }

        private void crmWorkspaceButton_Click(object sender, EventArgs e)
        {
            WorkspaceNavigation.OpenPage(this, "/crm");
        }

        private void companiesButton_Click(object sender, EventArgs e)
        {
            WorkspaceNavigation.OpenPage(this, "/crm/companies");
        }

        private void contactsButton_Click(object sender, EventArgs e)
        {
            WorkspaceNavigation.OpenPage(this, "/crm/contacts");
        }

        private void leadsButton_Click(object sender, EventArgs e)
        {
            WorkspaceNavigation.OpenPage(this, "/crm/leads");
        }

        private void dealsButton_Click(object sender, EventArgs e)
        {
            WorkspaceNavigation.OpenPage(this, "/crm/deals");
        }
    }
}
