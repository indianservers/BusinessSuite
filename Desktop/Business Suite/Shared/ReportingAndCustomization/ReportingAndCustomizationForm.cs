using System;
using System.Windows.Forms;

namespace Business_Suite
{
    public sealed partial class ReportingAndCustomizationForm : Form
    {
        public ReportingAndCustomizationForm()
        {
            InitializeComponent();
        }

        private void reportsButton_Click(object sender, EventArgs e)
        {
            WorkspaceNavigation.OpenPage(this, "/analytics/reports");
        }

        private void reportBuilderButton_Click(object sender, EventArgs e)
        {
            WorkspaceNavigation.OpenPage(this, "/analytics/report-builder");
        }

        private void settingsButton_Click(object sender, EventArgs e)
        {
            WorkspaceNavigation.OpenPage(this, "/settings");
        }
    }
}
