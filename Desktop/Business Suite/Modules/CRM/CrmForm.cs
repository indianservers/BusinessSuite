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
            OpenDirectory(CrmDirectoryKind.Companies);
        }

        private void companiesButton_Click(object sender, EventArgs e)
        {
            OpenDirectory(CrmDirectoryKind.Companies);
        }

        private void contactsButton_Click(object sender, EventArgs e)
        {
            OpenDirectory(CrmDirectoryKind.Contacts);
        }

        private void leadsButton_Click(object sender, EventArgs e)
        {
            using var form = new LeadsForm();
            form.ShowDialog(this);
        }

        private void potentialClientsButton_Click(object sender, EventArgs e)
        {
            using var form = new LeadsForm(potential: true);
            form.ShowDialog(this);
        }

        private void dealsButton_Click(object sender, EventArgs e)
        {
            try
            {
                using var form = new CrmDealsForm(DesktopDatabaseSettings.Load());
                form.ShowDialog(this);
            }
            catch (Exception error) when (error is ArgumentException or InvalidOperationException or IOException
                or UnauthorizedAccessException)
            {
                MessageBox.Show(this, error.Message, "Business Suite", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
        }

        private void quotationsButton_Click(object sender, EventArgs e)
        {
            try
            {
                using var form = new CrmQuotationsForm(DesktopDatabaseSettings.Load());
                form.ShowDialog(this);
            }
            catch (Exception error) when (error is ArgumentException or InvalidOperationException or IOException
                or UnauthorizedAccessException)
            {
                MessageBox.Show(this, error.Message, "Business Suite", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
        }

        private void mentionsButton_Click(object sender, EventArgs e)
        {
            try
            {
                using var form=new CrmMentionInboxForm(DesktopDatabaseSettings.Load());
                form.ShowDialog(this);
            }
            catch(Exception error) when(error is ArgumentException or InvalidOperationException or IOException or UnauthorizedAccessException)
            {
                MessageBox.Show(this,error.Message,"Business Suite",MessageBoxButtons.OK,MessageBoxIcon.Warning);
            }
        }

        private void customersButton_Click(object sender, EventArgs e) =>
            OpenDirectory(CrmDirectoryKind.Companies, "Customer");

        private void leadNotificationsButton_Click(object sender,EventArgs e)
        {
            using var form=new LeadNotificationInboxForm();
            form.ShowDialog(this);
        }

        private void leadScoringButton_Click(object sender,EventArgs e)
        {
            using var form=new LeadScoreBatchForm();
            form.ShowDialog(this);
        }

        private void sequenceTemplatesButton_Click(object sender,EventArgs e)
        {
            using var form=new LeadSequenceTemplatesForm();
            form.ShowDialog(this);
        }

        private void leadResponseRulesButton_Click(object sender,EventArgs e)
        {
            using var form=new LeadResponseWorkflowForm();
            form.ShowDialog(this);
        }

        private void leadStageSettingsButton_Click(object sender,EventArgs e)
        {
            using var form=new LeadStageSettingsForm();
            form.ShowDialog(this);
        }

        private void leadDueRemindersButton_Click(object sender,EventArgs e)
        {
            using var form=new LeadReminderProcessingForm();
            form.ShowDialog(this);
        }

        private void vendorsButton_Click(object sender, EventArgs e) =>
            OpenDirectory(CrmDirectoryKind.Companies, "Vendor");

        private void OpenDirectory(CrmDirectoryKind kind, string? role = null)
        {
            using var form = new CrmDirectoryForm(kind, role);
            form.ShowDialog(this);
        }
    }
}
