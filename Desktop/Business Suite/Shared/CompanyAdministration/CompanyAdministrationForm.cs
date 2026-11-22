using System;
using System.Windows.Forms;

namespace Business_Suite
{
    public sealed partial class CompanyAdministrationForm : Form
    {
        public CompanyAdministrationForm()
        {
            InitializeComponent();
        }

        private void settingsButton_Click(object sender, EventArgs e)
        {
            WorkspaceNavigation.OpenPage(this, "/settings");
        }

        private void companyProfileButton_Click(object sender, EventArgs e)
        {
            WorkspaceNavigation.OpenPage(this, "/settings/company-profile");
        }

        private void branchesButton_Click(object sender, EventArgs e)
        {
            WorkspaceNavigation.OpenPage(this, "/settings/branches");
        }

        private void usersButton_Click(object sender, EventArgs e)
        {
            WorkspaceNavigation.OpenPage(this, "/settings/users");
        }
    }
}
