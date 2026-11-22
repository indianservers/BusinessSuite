using System;
using System.Windows.Forms;

namespace Business_Suite
{
    public sealed partial class DocumentsAndCommunicationForm : Form
    {
        public DocumentsAndCommunicationForm()
        {
            InitializeComponent();
        }

        private void communicationHubButton_Click(object sender, EventArgs e)
        {
            WorkspaceNavigation.OpenPage(this, "/crm/communication-hub");
        }

        private void crmFilesButton_Click(object sender, EventArgs e)
        {
            WorkspaceNavigation.OpenPage(this, "/crm/files");
        }
    }
}
