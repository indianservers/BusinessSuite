#nullable disable
using System;
using System.Drawing;
using System.Windows.Forms;

namespace Business_Suite
{
    partial class CompanyAdministrationForm
    {
        private void InitializeComponent()
        {
            this.headingLabel = new Label();
            this.descriptionLabel = new Label();
            this.settingsButton = new Button();
            this.companyProfileButton = new Button();
            this.branchesButton = new Button();
            this.usersButton = new Button();
            this.SuspendLayout();
            // headingLabel
            this.headingLabel.Location = new Point(24, 24);
            this.headingLabel.Size = new Size(550, 43);
            this.headingLabel.Name = "headingLabel";
            this.headingLabel.Text = "Company administration";
            this.headingLabel.Font = new Font("Segoe UI Semibold", 21F);
            // descriptionLabel
            this.descriptionLabel.Location = new Point(24, 74);
            this.descriptionLabel.Size = new Size(550, 31);
            this.descriptionLabel.Name = "descriptionLabel";
            this.descriptionLabel.Text = "Company details, branches and access management.";
            // settingsButton
            this.settingsButton.Location = new Point(24, 112);
            this.settingsButton.Size = new Size(240, 42);
            this.settingsButton.Name = "settingsButton";
            this.settingsButton.Text = "Settings";
            this.settingsButton.FlatStyle = FlatStyle.Flat;
            this.settingsButton.BackColor = Color.White;
            this.settingsButton.UseVisualStyleBackColor = false;
            this.settingsButton.TabIndex = 0;
            this.settingsButton.Click += this.settingsButton_Click;
            // companyProfileButton
            this.companyProfileButton.Location = new Point(282, 112);
            this.companyProfileButton.Size = new Size(240, 42);
            this.companyProfileButton.Name = "companyProfileButton";
            this.companyProfileButton.Text = "Company profile";
            this.companyProfileButton.FlatStyle = FlatStyle.Flat;
            this.companyProfileButton.BackColor = Color.White;
            this.companyProfileButton.UseVisualStyleBackColor = false;
            this.companyProfileButton.TabIndex = 1;
            this.companyProfileButton.Click += this.companyProfileButton_Click;
            // branchesButton
            this.branchesButton.Location = new Point(24, 164);
            this.branchesButton.Size = new Size(240, 42);
            this.branchesButton.Name = "branchesButton";
            this.branchesButton.Text = "Branches";
            this.branchesButton.FlatStyle = FlatStyle.Flat;
            this.branchesButton.BackColor = Color.White;
            this.branchesButton.UseVisualStyleBackColor = false;
            this.branchesButton.TabIndex = 2;
            this.branchesButton.Click += this.branchesButton_Click;
            // usersButton
            this.usersButton.Location = new Point(282, 164);
            this.usersButton.Size = new Size(240, 42);
            this.usersButton.Name = "usersButton";
            this.usersButton.Text = "Users";
            this.usersButton.FlatStyle = FlatStyle.Flat;
            this.usersButton.BackColor = Color.White;
            this.usersButton.UseVisualStyleBackColor = false;
            this.usersButton.TabIndex = 3;
            this.usersButton.Click += this.usersButton_Click;
            this.Controls.Add(this.headingLabel);
            this.Controls.Add(this.descriptionLabel);
            this.Controls.Add(this.settingsButton);
            this.Controls.Add(this.companyProfileButton);
            this.Controls.Add(this.branchesButton);
            this.Controls.Add(this.usersButton);
            this.AutoScaleDimensions = new SizeF(96F, 96F);
            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.ClientSize = new Size(600, 350);
            this.StartPosition = FormStartPosition.CenterParent;
            this.BackColor = Color.FromArgb(243, 246, 251);
            this.Font = new Font("Segoe UI", 10F);
            this.Text = "Business Suite | Company administration";
            this.Name = "CompanyAdministrationForm";
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Label headingLabel;
        private Label descriptionLabel;
        private Button settingsButton;
        private Button companyProfileButton;
        private Button branchesButton;
        private Button usersButton;
    }
}
