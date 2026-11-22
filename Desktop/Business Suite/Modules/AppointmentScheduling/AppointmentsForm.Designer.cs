#nullable disable
using System;
using System.Drawing;
using System.Windows.Forms;

namespace Business_Suite
{
    partial class AppointmentsForm
    {
        private void InitializeComponent()
        {
            this.headingLabel = new Label();
            this.descriptionLabel = new Label();
            this.appointmentSchedulerButton = new Button();
            this.SuspendLayout();
            // headingLabel
            this.headingLabel.Location = new Point(24, 24);
            this.headingLabel.Size = new Size(550, 43);
            this.headingLabel.Name = "headingLabel";
            this.headingLabel.Text = "Appointments";
            this.headingLabel.Font = new Font("Segoe UI Semibold", 21F);
            // descriptionLabel
            this.descriptionLabel.Location = new Point(24, 74);
            this.descriptionLabel.Size = new Size(550, 31);
            this.descriptionLabel.Name = "descriptionLabel";
            this.descriptionLabel.Text = "Schedule services and customer bookings.";
            // appointmentSchedulerButton
            this.appointmentSchedulerButton.Location = new Point(24, 112);
            this.appointmentSchedulerButton.Size = new Size(240, 42);
            this.appointmentSchedulerButton.Name = "appointmentSchedulerButton";
            this.appointmentSchedulerButton.Text = "Appointment scheduler";
            this.appointmentSchedulerButton.FlatStyle = FlatStyle.Flat;
            this.appointmentSchedulerButton.BackColor = Color.White;
            this.appointmentSchedulerButton.UseVisualStyleBackColor = false;
            this.appointmentSchedulerButton.TabIndex = 0;
            this.appointmentSchedulerButton.Click += this.appointmentSchedulerButton_Click;
            this.Controls.Add(this.headingLabel);
            this.Controls.Add(this.descriptionLabel);
            this.Controls.Add(this.appointmentSchedulerButton);
            this.AutoScaleDimensions = new SizeF(96F, 96F);
            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.ClientSize = new Size(600, 350);
            this.StartPosition = FormStartPosition.CenterParent;
            this.BackColor = Color.FromArgb(243, 246, 251);
            this.Font = new Font("Segoe UI", 10F);
            this.Text = "Business Suite | Appointments";
            this.Name = "AppointmentsForm";
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Label headingLabel;
        private Label descriptionLabel;
        private Button appointmentSchedulerButton;
    }
}
