using System;
using System.Windows.Forms;

namespace Business_Suite
{
    public sealed partial class ProjectManagementForm : Form
    {
        public ProjectManagementForm()
        {
            InitializeComponent();
        }

        private void projectWorkspaceButton_Click(object sender, EventArgs e)
        {
            WorkspaceNavigation.OpenPage(this, "/pms");
        }

        private void workspacesButton_Click(object sender, EventArgs e)
        {
            WorkspaceNavigation.OpenPage(this, "/pms/workspaces");
        }

        private void myWorkButton_Click(object sender, EventArgs e)
        {
            WorkspaceNavigation.OpenPage(this, "/pms/my-work");
        }
    }
}
