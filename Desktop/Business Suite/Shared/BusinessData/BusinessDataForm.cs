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
            using var form = new CrmDirectoryForm(CrmDirectoryKind.Companies);
            form.ShowDialog(this);
        }

        private void contactsButton_Click(object sender, EventArgs e)
        {
            using var form = new CrmDirectoryForm(CrmDirectoryKind.Contacts);
            form.ShowDialog(this);
        }

        private void workspacesButton_Click(object sender, EventArgs e)
        {
            OpenScoped(settings => new PmsWorkspacesForm(settings));
        }

        private void catalogButton_Click(object sender, EventArgs e)
        {
            OpenScoped(settings => new SharedCatalogForm(settings));
        }

        private void OpenScoped(Func<DesktopDatabaseSettings, Form> create)
        {
            try
            {
                using var form = create(DesktopDatabaseSettings.Load());
                form.ShowDialog(this);
            }
            catch (Exception error) when (error is ArgumentException or IOException or UnauthorizedAccessException
                or InvalidOperationException)
            {
                MessageBox.Show(this, error.Message, "Business Suite", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
        }
    }
}
