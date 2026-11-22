using System;
using System.Windows.Forms;

namespace Business_Suite
{
    public sealed partial class FinanceAndAccountingForm : Form
    {
        public FinanceAndAccountingForm()
        {
            InitializeComponent();
        }

        private void financeWorkspaceButton_Click(object sender, EventArgs e)
        {
            WorkspaceNavigation.OpenPage(this, "/fam");
        }

        private void ledgersButton_Click(object sender, EventArgs e)
        {
            WorkspaceNavigation.OpenPage(this, "/fam/ledgers");
        }

        private void workspacesButton_Click(object sender, EventArgs e)
        {
            WorkspaceNavigation.OpenPage(this, "/fam/workspaces");
        }
    }
}
