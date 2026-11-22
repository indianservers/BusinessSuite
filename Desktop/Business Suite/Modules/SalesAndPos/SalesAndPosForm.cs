using System;
using System.Windows.Forms;

namespace Business_Suite
{
    public sealed partial class SalesAndPosForm : Form
    {
        public SalesAndPosForm()
        {
            InitializeComponent();
        }

        private void salesWorkspaceButton_Click(object sender, EventArgs e)
        {
            WorkspaceNavigation.OpenPage(this, "/srm");
        }

        private void appointmentsButton_Click(object sender, EventArgs e)
        {
            WorkspaceNavigation.OpenPage(this, "/srm/appointments");
        }
    }
}
