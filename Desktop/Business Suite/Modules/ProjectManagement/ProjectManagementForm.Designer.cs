#nullable disable
using System;
using System.Drawing;
using System.Windows.Forms;

namespace Business_Suite
{
    partial class ProjectManagementForm
    {
        private void InitializeComponent()
        {
            this.headingLabel = new Label();
            this.descriptionLabel = new Label();
            this.projectWorkspaceButton = new Button();
            this.workspacesButton = new Button();
            this.myWorkButton = new Button();
            this.SuspendLayout();
            // headingLabel
            this.headingLabel.Location = new Point(24, 24);
            this.headingLabel.Size = new Size(550, 43);
            this.headingLabel.Name = "headingLabel";
            this.headingLabel.Text = "KaryaFlow PMS";
            this.headingLabel.Font = new Font("Segoe UI Semibold", 21F);
            // descriptionLabel
            this.descriptionLabel.Location = new Point(24, 74);
            this.descriptionLabel.Size = new Size(550, 31);
            this.descriptionLabel.Name = "descriptionLabel";
            this.descriptionLabel.Text = "Projects, workspaces and tasks.";
            // projectWorkspaceButton
            this.projectWorkspaceButton.Location = new Point(24, 112);
            this.projectWorkspaceButton.Size = new Size(240, 42);
            this.projectWorkspaceButton.Name = "projectWorkspaceButton";
            this.projectWorkspaceButton.Text = "Project workspace";
            this.projectWorkspaceButton.FlatStyle = FlatStyle.Flat;
            this.projectWorkspaceButton.BackColor = Color.White;
            this.projectWorkspaceButton.UseVisualStyleBackColor = false;
            this.projectWorkspaceButton.TabIndex = 0;
            this.projectWorkspaceButton.Click += this.projectWorkspaceButton_Click;
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
            // myWorkButton
            this.myWorkButton.Location = new Point(24, 164);
            this.myWorkButton.Size = new Size(240, 42);
            this.myWorkButton.Name = "myWorkButton";
            this.myWorkButton.Text = "My work";
            this.myWorkButton.FlatStyle = FlatStyle.Flat;
            this.myWorkButton.BackColor = Color.White;
            this.myWorkButton.UseVisualStyleBackColor = false;
            this.myWorkButton.TabIndex = 2;
            this.myWorkButton.Click += this.myWorkButton_Click;
            this.Controls.Add(this.headingLabel);
            this.Controls.Add(this.descriptionLabel);
            this.Controls.Add(this.projectWorkspaceButton);
            this.Controls.Add(this.workspacesButton);
            this.Controls.Add(this.myWorkButton);
            this.AutoScaleDimensions = new SizeF(96F, 96F);
            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.ClientSize = new Size(600, 350);
            this.StartPosition = FormStartPosition.CenterParent;
            this.BackColor = Color.FromArgb(243, 246, 251);
            this.Font = new Font("Segoe UI", 10F);
            this.Text = "Business Suite | KaryaFlow PMS";
            this.Name = "ProjectManagementForm";
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Label headingLabel;
        private Label descriptionLabel;
        private Button projectWorkspaceButton;
        private Button workspacesButton;
        private Button myWorkButton;
    }
}
