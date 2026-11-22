using System;
using System.Windows.Forms;

namespace Business_Suite
{
    public sealed partial class AppointmentsForm : Form
    {
        public AppointmentsForm()
        {
            InitializeComponent();
        }

        private void appointmentSchedulerButton_Click(object sender, EventArgs e)
        {
            WorkspaceNavigation.OpenPage(this, "/srm/appointments");
        }
    }
}
