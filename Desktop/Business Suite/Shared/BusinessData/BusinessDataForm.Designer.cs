#nullable disable
using System;
using System.Drawing;
using System.Windows.Forms;

namespace Business_Suite
{
    partial class BusinessDataForm
    {
        private void InitializeComponent()
        {
            this.headingLabel = new Label();
            this.descriptionLabel = new Label();
            this.companiesButton = new Button();
            this.contactsButton = new Button();
            this.workspacesButton = new Button();
            this.catalogButton = new Telerik.WinControls.UI.RadButton();
            ((System.ComponentModel.ISupportInitialize)this.catalogButton).BeginInit();
            this.SuspendLayout();
            // headingLabel
            this.headingLabel.Location = new Point(24, 24);
            this.headingLabel.Size = new Size(550, 43);
            this.headingLabel.Name = "headingLabel";
            this.headingLabel.Text = "Shared business data";
            this.headingLabel.Font = new Font("Segoe UI Semibold", 21F);
            // descriptionLabel
            this.descriptionLabel.Location = new Point(24, 74);
            this.descriptionLabel.Size = new Size(550, 31);
            this.descriptionLabel.Name = "descriptionLabel";
            this.descriptionLabel.Text = "Company, contact, catalog and workspace directories.";
            // companiesButton
            this.companiesButton.Location = new Point(24, 112);
            this.companiesButton.Size = new Size(240, 42);
            this.companiesButton.Name = "companiesButton";
            this.companiesButton.Text = "Companies";
            this.companiesButton.FlatStyle = FlatStyle.Flat;
            this.companiesButton.BackColor = Color.White;
            this.companiesButton.UseVisualStyleBackColor = false;
            this.companiesButton.TabIndex = 0;
            this.companiesButton.Click += this.companiesButton_Click;
            // contactsButton
            this.contactsButton.Location = new Point(282, 112);
            this.contactsButton.Size = new Size(240, 42);
            this.contactsButton.Name = "contactsButton";
            this.contactsButton.Text = "Contacts";
            this.contactsButton.FlatStyle = FlatStyle.Flat;
            this.contactsButton.BackColor = Color.White;
            this.contactsButton.UseVisualStyleBackColor = false;
            this.contactsButton.TabIndex = 1;
            this.contactsButton.Click += this.contactsButton_Click;
            // workspacesButton
            this.workspacesButton.Location = new Point(24, 164);
            this.workspacesButton.Size = new Size(240, 42);
            this.workspacesButton.Name = "workspacesButton";
            this.workspacesButton.Text = "Workspaces";
            this.workspacesButton.FlatStyle = FlatStyle.Flat;
            this.workspacesButton.BackColor = Color.White;
            this.workspacesButton.UseVisualStyleBackColor = false;
            this.workspacesButton.TabIndex = 2;
            this.workspacesButton.Click += this.workspacesButton_Click;
            this.catalogButton.Location = new Point(282, 164);
            this.catalogButton.Size = new Size(240, 42);
            this.catalogButton.Name = "catalogButton";
            this.catalogButton.Text = "Products and Services";
            this.catalogButton.TabIndex = 3;
            this.catalogButton.Click += this.catalogButton_Click;
            this.Controls.Add(this.headingLabel);
            this.Controls.Add(this.descriptionLabel);
            this.Controls.Add(this.companiesButton);
            this.Controls.Add(this.contactsButton);
            this.Controls.Add(this.workspacesButton);
            this.Controls.Add(this.catalogButton);
            this.AutoScaleDimensions = new SizeF(96F, 96F);
            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.ClientSize = new Size(600, 350);
            this.StartPosition = FormStartPosition.CenterParent;
            this.BackColor = Color.FromArgb(243, 246, 251);
            this.Font = new Font("Segoe UI", 10F);
            this.Text = "Business Suite | Shared business data";
            this.Name = "BusinessDataForm";
            ((System.ComponentModel.ISupportInitialize)this.catalogButton).EndInit();
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Label headingLabel;
        private Label descriptionLabel;
        private Button companiesButton;
        private Button contactsButton;
        private Button workspacesButton;
        private Telerik.WinControls.UI.RadButton catalogButton;
    }
}
