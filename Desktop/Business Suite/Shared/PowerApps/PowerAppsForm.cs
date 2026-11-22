using System;
using System.Windows.Forms;

namespace Business_Suite
{
    public sealed partial class PowerAppsForm : Form
    {
        public PowerAppsForm()
        {
            InitializeComponent();
        }

        private void powerAppsButton_Click(object sender, EventArgs e)
        {
            WorkspaceNavigation.OpenPage(this, "/power-apps");
        }

        private void automationsButton_Click(object sender, EventArgs e)
        {
            WorkspaceNavigation.OpenPage(this, "/power-apps/automations");
        }

        private void approvalsButton_Click(object sender, EventArgs e)
        {
            WorkspaceNavigation.OpenPage(this, "/power-apps/approvals");
        }
    }
}
