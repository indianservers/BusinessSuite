#nullable disable
using System;
using System.Drawing;
using System.Windows.Forms;

namespace Business_Suite
{
    partial class CrmForm
    {
        private void InitializeComponent()
        {
            this.headingLabel = new Label();
            this.descriptionLabel = new Label();
            this.crmWorkspaceButton = new Button();
            this.companiesButton = new Button();
            this.contactsButton = new Button();
            this.leadsButton = new Button();
            this.dealsButton = new Button();
            this.SuspendLayout();
            // headingLabel
            this.headingLabel.Location = new Point(24, 24);
            this.headingLabel.Size = new Size(550, 43);
            this.headingLabel.Name = "headingLabel";
            this.headingLabel.Text = "VyaparaCRM";
            this.headingLabel.Font = new Font("Segoe UI Semibold", 21F);
            // descriptionLabel
            this.descriptionLabel.Location = new Point(24, 74);
            this.descriptionLabel.Size = new Size(550, 31);
            this.descriptionLabel.Name = "descriptionLabel";
            this.descriptionLabel.Text = "Customers, leads, contacts and deals.";
            // crmWorkspaceButton
            this.crmWorkspaceButton.Location = new Point(24, 112);
            this.crmWorkspaceButton.Size = new Size(240, 42);
            this.crmWorkspaceButton.Name = "crmWorkspaceButton";
            this.crmWorkspaceButton.Text = "CRM workspace";
            this.crmWorkspaceButton.FlatStyle = FlatStyle.Flat;
            this.crmWorkspaceButton.BackColor = Color.White;
            this.crmWorkspaceButton.UseVisualStyleBackColor = false;
            this.crmWorkspaceButton.TabIndex = 0;
            this.crmWorkspaceButton.Click += this.crmWorkspaceButton_Click;
            // companiesButton
            this.companiesButton.Location = new Point(282, 112);
            this.companiesButton.Size = new Size(240, 42);
            this.companiesButton.Name = "companiesButton";
            this.companiesButton.Text = "Companies";
            this.companiesButton.FlatStyle = FlatStyle.Flat;
            this.companiesButton.BackColor = Color.White;
            this.companiesButton.UseVisualStyleBackColor = false;
            this.companiesButton.TabIndex = 1;
            this.companiesButton.Click += this.companiesButton_Click;
            // contactsButton
            this.contactsButton.Location = new Point(24, 164);
            this.contactsButton.Size = new Size(240, 42);
            this.contactsButton.Name = "contactsButton";
            this.contactsButton.Text = "Contacts";
            this.contactsButton.FlatStyle = FlatStyle.Flat;
            this.contactsButton.BackColor = Color.White;
            this.contactsButton.UseVisualStyleBackColor = false;
            this.contactsButton.TabIndex = 2;
            this.contactsButton.Click += this.contactsButton_Click;
            // leadsButton
            this.leadsButton.Location = new Point(282, 164);
            this.leadsButton.Size = new Size(240, 42);
            this.leadsButton.Name = "leadsButton";
            this.leadsButton.Text = "Leads";
            this.leadsButton.FlatStyle = FlatStyle.Flat;
            this.leadsButton.BackColor = Color.White;
            this.leadsButton.UseVisualStyleBackColor = false;
            this.leadsButton.TabIndex = 3;
            this.leadsButton.Click += this.leadsButton_Click;
            // dealsButton
            this.dealsButton.Location = new Point(24, 216);
            this.dealsButton.Size = new Size(240, 42);
            this.dealsButton.Name = "dealsButton";
            this.dealsButton.Text = "Deals";
            this.dealsButton.FlatStyle = FlatStyle.Flat;
            this.dealsButton.BackColor = Color.White;
            this.dealsButton.UseVisualStyleBackColor = false;
            this.dealsButton.TabIndex = 4;
            this.dealsButton.Click += this.dealsButton_Click;
            this.Controls.Add(this.headingLabel);
            this.Controls.Add(this.descriptionLabel);
            this.Controls.Add(this.crmWorkspaceButton);
            this.Controls.Add(this.companiesButton);
            this.Controls.Add(this.contactsButton);
            this.Controls.Add(this.leadsButton);
            this.Controls.Add(this.dealsButton);
            this.AutoScaleDimensions = new SizeF(96F, 96F);
            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.ClientSize = new Size(600, 350);
            this.StartPosition = FormStartPosition.CenterParent;
            this.BackColor = Color.FromArgb(243, 246, 251);
            this.Font = new Font("Segoe UI", 10F);
            this.Text = "Business Suite | VyaparaCRM";
            this.Name = "CrmForm";
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Label headingLabel;
        private Label descriptionLabel;
        private Button crmWorkspaceButton;
        private Button companiesButton;
        private Button contactsButton;
        private Button leadsButton;
        private Button dealsButton;
    }
}
