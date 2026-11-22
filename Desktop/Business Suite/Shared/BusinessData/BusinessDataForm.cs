using System;
using System.Windows.Forms;

namespace Business_Suite
{
    public sealed partial class BusinessDataForm : Form
    {
        public BusinessDataForm()
        {
            InitializeComponent();
        }

        private void companiesButton_Click(object sender, EventArgs e)
        {
            WorkspaceNavigation.OpenPage(this, "/crm/companies");
        }

        private void contactsButton_Click(object sender, EventArgs e)
        {
            WorkspaceNavigation.OpenPage(this, "/crm/contacts");
        }

        private void workspacesButton_Click(object sender, EventArgs e)
        {
            WorkspaceNavigation.OpenPage(this, "/pms/workspaces");
        }
    }
}
