#nullable disable
using System;
using System.Drawing;
using System.Windows.Forms;

namespace Business_Suite
{
    partial class HrmsForm
    {
        private void InitializeComponent()
        {
            this.headingLabel = new Label();
            this.descriptionLabel = new Label();
            this.hrWorkspaceButton = new Button();
            this.workspacesButton = new Button();
            this.SuspendLayout();
            // headingLabel
            this.headingLabel.Location = new Point(24, 24);
            this.headingLabel.Size = new Size(550, 43);
            this.headingLabel.Name = "headingLabel";
            this.headingLabel.Text = "AI HRMS";
            this.headingLabel.Font = new Font("Segoe UI Semibold", 21F);
            // descriptionLabel
            this.descriptionLabel.Location = new Point(24, 74);
            this.descriptionLabel.Size = new Size(550, 31);
            this.descriptionLabel.Name = "descriptionLabel";
            this.descriptionLabel.Text = "Employees, attendance, leave and payroll.";
            // hrWorkspaceButton
            this.hrWorkspaceButton.Location = new Point(24, 112);
            this.hrWorkspaceButton.Size = new Size(240, 42);
            this.hrWorkspaceButton.Name = "hrWorkspaceButton";
            this.hrWorkspaceButton.Text = "HR workspace";
            this.hrWorkspaceButton.FlatStyle = FlatStyle.Flat;
            this.hrWorkspaceButton.BackColor = Color.White;
            this.hrWorkspaceButton.UseVisualStyleBackColor = false;
            this.hrWorkspaceButton.TabIndex = 0;
            this.hrWorkspaceButton.Click += this.hrWorkspaceButton_Click;
            // workspacesButton
            this.workspacesButton.Location = new Point(282, 112);
            this.workspacesButton.Size = new Size(240, 42);
            this.workspacesButton.Name = "workspacesButton";
            this.workspacesButton.Text = "Workspaces";
            this.workspacesButton.FlatStyle = FlatStyle.Flat;
            this.workspacesButton.BackColor = Color.White;
            this.workspacesButton.UseVisualStyleBackColor = false;
            this.workspacesButton.TabIndex = 1;
            this.workspacesButton.Click += this.workspacesButton_Click;
            this.Controls.Add(this.headingLabel);
            this.Controls.Add(this.descriptionLabel);
            this.Controls.Add(this.hrWorkspaceButton);
            this.Controls.Add(this.workspacesButton);
            this.AutoScaleDimensions = new SizeF(96F, 96F);
            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.ClientSize = new Size(600, 350);
            this.StartPosition = FormStartPosition.CenterParent;
            this.BackColor = Color.FromArgb(243, 246, 251);
            this.Font = new Font("Segoe UI", 10F);
            this.Text = "Business Suite | AI HRMS";
            this.Name = "HrmsForm";
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Label headingLabel;
        private Label descriptionLabel;
        private Button hrWorkspaceButton;
        private Button workspacesButton;
    }
}
