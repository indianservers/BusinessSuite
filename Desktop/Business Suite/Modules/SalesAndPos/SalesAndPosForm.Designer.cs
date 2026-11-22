#nullable disable
using System;
using System.Drawing;
using System.Windows.Forms;

namespace Business_Suite
{
    partial class SalesAndPosForm
    {
        private void InitializeComponent()
        {
            this.headingLabel = new Label();
            this.descriptionLabel = new Label();
            this.salesWorkspaceButton = new Button();
            this.appointmentsButton = new Button();
            this.SuspendLayout();
            // headingLabel
            this.headingLabel.Location = new Point(24, 24);
            this.headingLabel.Size = new Size(550, 43);
            this.headingLabel.Name = "headingLabel";
            this.headingLabel.Text = "Sales & POS";
            this.headingLabel.Font = new Font("Segoe UI Semibold", 21F);
            // descriptionLabel
            this.descriptionLabel.Location = new Point(24, 74);
            this.descriptionLabel.Size = new Size(550, 31);
            this.descriptionLabel.Name = "descriptionLabel";
            this.descriptionLabel.Text = "Sales, checkout and inventory operations.";
            // salesWorkspaceButton
            this.salesWorkspaceButton.Location = new Point(24, 112);
            this.salesWorkspaceButton.Size = new Size(240, 42);
            this.salesWorkspaceButton.Name = "salesWorkspaceButton";
            this.salesWorkspaceButton.Text = "Sales workspace";
            this.salesWorkspaceButton.FlatStyle = FlatStyle.Flat;
            this.salesWorkspaceButton.BackColor = Color.White;
            this.salesWorkspaceButton.UseVisualStyleBackColor = false;
            this.salesWorkspaceButton.TabIndex = 0;
            this.salesWorkspaceButton.Click += this.salesWorkspaceButton_Click;
            // appointmentsButton
            this.appointmentsButton.Location = new Point(282, 112);
            this.appointmentsButton.Size = new Size(240, 42);
            this.appointmentsButton.Name = "appointmentsButton";
            this.appointmentsButton.Text = "Appointments";
            this.appointmentsButton.FlatStyle = FlatStyle.Flat;
            this.appointmentsButton.BackColor = Color.White;
            this.appointmentsButton.UseVisualStyleBackColor = false;
            this.appointmentsButton.TabIndex = 1;
            this.appointmentsButton.Click += this.appointmentsButton_Click;
            this.Controls.Add(this.headingLabel);
            this.Controls.Add(this.descriptionLabel);
            this.Controls.Add(this.salesWorkspaceButton);
            this.Controls.Add(this.appointmentsButton);
            this.AutoScaleDimensions = new SizeF(96F, 96F);
            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.ClientSize = new Size(600, 350);
            this.StartPosition = FormStartPosition.CenterParent;
            this.BackColor = Color.FromArgb(243, 246, 251);
            this.Font = new Font("Segoe UI", 10F);
            this.Text = "Business Suite | Sales & POS";
            this.Name = "SalesAndPosForm";
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Label headingLabel;
        private Label descriptionLabel;
        private Button salesWorkspaceButton;
        private Button appointmentsButton;
    }
}
