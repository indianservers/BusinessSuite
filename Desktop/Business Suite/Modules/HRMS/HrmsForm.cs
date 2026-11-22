using System;
using System.Windows.Forms;

namespace Business_Suite
{
    public sealed partial class HrmsForm : Form
    {
        public HrmsForm()
        {
            InitializeComponent();
        }

        private void hrWorkspaceButton_Click(object sender, EventArgs e)
        {
            WorkspaceNavigation.OpenPage(this, "/hrms");
        }

        private void workspacesButton_Click(object sender, EventArgs e)
        {
            WorkspaceNavigation.OpenPage(this, "/hrms/workspaces");
        }
    }
}
