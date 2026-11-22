#nullable disable
using System;
using System.Drawing;
using System.Windows.Forms;

namespace Business_Suite
{
    partial class MainForm
    {
        private void InitializeComponent()
        {
            this.headingLabel = new Label();
            this.modulesLabel = new Label();
            this.sharedLabel = new Label();
            this.appointmentsButton = new Button();
            this.crmButton = new Button();
            this.financeAndAccountingButton = new Button();
            this.hrmsButton = new Button();
            this.projectManagementButton = new Button();
            this.salesAndPosButton = new Button();
            this.businessDataButton = new Button();
            this.companyAdministrationButton = new Button();
            this.documentsAndCommunicationButton = new Button();
            this.powerAppsButton = new Button();
            this.reportingAndCustomizationButton = new Button();
            this.settingsButton = new Button();
            this.companiesGridButton = new Button();
            this.SuspendLayout();
            // headingLabel
            this.headingLabel.Location = new Point(26, 26);
            this.headingLabel.Size = new Size(700, 55);
            this.headingLabel.Name = "headingLabel";
            this.headingLabel.Text = "Business Suite";
            this.headingLabel.Font = new Font("Segoe UI Semibold", 28F);
            // modulesLabel
            this.modulesLabel.Location = new Point(26, 98);
            this.modulesLabel.Size = new Size(345, 30);
            this.modulesLabel.Name = "modulesLabel";
            this.modulesLabel.Text = "Modules";
            this.modulesLabel.Font = new Font("Segoe UI Semibold", 14F);
            // sharedLabel
            this.sharedLabel.Location = new Point(430, 98);
            this.sharedLabel.Size = new Size(345, 30);
            this.sharedLabel.Name = "sharedLabel";
            this.sharedLabel.Text = "Shared";
            this.sharedLabel.Font = new Font("Segoe UI Semibold", 14F);
            // appointmentsButton
            this.appointmentsButton.Location = new Point(26, 134);
            this.appointmentsButton.Size = new Size(284, 43);
            this.appointmentsButton.Name = "appointmentsButton";
            this.appointmentsButton.Text = "Appointments";
            this.appointmentsButton.TextAlign = ContentAlignment.MiddleLeft;
            this.appointmentsButton.Padding = new Padding(10, 0, 0, 0);
            this.appointmentsButton.FlatStyle = FlatStyle.Flat;
            this.appointmentsButton.BackColor = Color.White;
            this.appointmentsButton.UseVisualStyleBackColor = false;
            this.appointmentsButton.FlatAppearance.BorderColor = Color.FromArgb(210, 221, 237);
            this.appointmentsButton.Click += this.appointmentsButton_Click;
            // crmButton
            this.crmButton.Location = new Point(26, 183);
            this.crmButton.Size = new Size(284, 43);
            this.crmButton.Name = "crmButton";
            this.crmButton.Text = "VyaparaCRM";
            this.crmButton.TextAlign = ContentAlignment.MiddleLeft;
            this.crmButton.Padding = new Padding(10, 0, 0, 0);
            this.crmButton.FlatStyle = FlatStyle.Flat;
            this.crmButton.BackColor = Color.White;
            this.crmButton.UseVisualStyleBackColor = false;
            this.crmButton.FlatAppearance.BorderColor = Color.FromArgb(210, 221, 237);
            this.crmButton.Click += this.crmButton_Click;
            // financeAndAccountingButton
            this.financeAndAccountingButton.Location = new Point(26, 232);
            this.financeAndAccountingButton.Size = new Size(284, 43);
            this.financeAndAccountingButton.Name = "financeAndAccountingButton";
            this.financeAndAccountingButton.Text = "Finance & Accounting";
            this.financeAndAccountingButton.TextAlign = ContentAlignment.MiddleLeft;
            this.financeAndAccountingButton.Padding = new Padding(10, 0, 0, 0);
            this.financeAndAccountingButton.FlatStyle = FlatStyle.Flat;
            this.financeAndAccountingButton.BackColor = Color.White;
            this.financeAndAccountingButton.UseVisualStyleBackColor = false;
            this.financeAndAccountingButton.FlatAppearance.BorderColor = Color.FromArgb(210, 221, 237);
            this.financeAndAccountingButton.Click += this.financeAndAccountingButton_Click;
            // hrmsButton
            this.hrmsButton.Location = new Point(26, 281);
            this.hrmsButton.Size = new Size(284, 43);
            this.hrmsButton.Name = "hrmsButton";
            this.hrmsButton.Text = "AI HRMS";
            this.hrmsButton.TextAlign = ContentAlignment.MiddleLeft;
            this.hrmsButton.Padding = new Padding(10, 0, 0, 0);
            this.hrmsButton.FlatStyle = FlatStyle.Flat;
            this.hrmsButton.BackColor = Color.White;
            this.hrmsButton.UseVisualStyleBackColor = false;
            this.hrmsButton.FlatAppearance.BorderColor = Color.FromArgb(210, 221, 237);
            this.hrmsButton.Click += this.hrmsButton_Click;
            // projectManagementButton
            this.projectManagementButton.Location = new Point(26, 330);
            this.projectManagementButton.Size = new Size(284, 43);
            this.projectManagementButton.Name = "projectManagementButton";
            this.projectManagementButton.Text = "KaryaFlow PMS";
            this.projectManagementButton.TextAlign = ContentAlignment.MiddleLeft;
            this.projectManagementButton.Padding = new Padding(10, 0, 0, 0);
            this.projectManagementButton.FlatStyle = FlatStyle.Flat;
            this.projectManagementButton.BackColor = Color.White;
            this.projectManagementButton.UseVisualStyleBackColor = false;
            this.projectManagementButton.FlatAppearance.BorderColor = Color.FromArgb(210, 221, 237);
            this.projectManagementButton.Click += this.projectManagementButton_Click;
            // salesAndPosButton
            this.salesAndPosButton.Location = new Point(26, 379);
            this.salesAndPosButton.Size = new Size(284, 43);
            this.salesAndPosButton.Name = "salesAndPosButton";
            this.salesAndPosButton.Text = "Sales & POS";
            this.salesAndPosButton.TextAlign = ContentAlignment.MiddleLeft;
            this.salesAndPosButton.Padding = new Padding(10, 0, 0, 0);
            this.salesAndPosButton.FlatStyle = FlatStyle.Flat;
            this.salesAndPosButton.BackColor = Color.White;
            this.salesAndPosButton.UseVisualStyleBackColor = false;
            this.salesAndPosButton.FlatAppearance.BorderColor = Color.FromArgb(210, 221, 237);
            this.salesAndPosButton.Click += this.salesAndPosButton_Click;
            // businessDataButton
            this.businessDataButton.Location = new Point(430, 134);
            this.businessDataButton.Size = new Size(284, 43);
            this.businessDataButton.Name = "businessDataButton";
            this.businessDataButton.Text = "Shared business data";
            this.businessDataButton.TextAlign = ContentAlignment.MiddleLeft;
            this.businessDataButton.Padding = new Padding(10, 0, 0, 0);
            this.businessDataButton.FlatStyle = FlatStyle.Flat;
            this.businessDataButton.BackColor = Color.White;
            this.businessDataButton.UseVisualStyleBackColor = false;
            this.businessDataButton.FlatAppearance.BorderColor = Color.FromArgb(210, 221, 237);
            this.businessDataButton.Click += this.businessDataButton_Click;
            // companyAdministrationButton
            this.companyAdministrationButton.Location = new Point(430, 183);
            this.companyAdministrationButton.Size = new Size(284, 43);
            this.companyAdministrationButton.Name = "companyAdministrationButton";
            this.companyAdministrationButton.Text = "Company administration";
            this.companyAdministrationButton.TextAlign = ContentAlignment.MiddleLeft;
            this.companyAdministrationButton.Padding = new Padding(10, 0, 0, 0);
            this.companyAdministrationButton.FlatStyle = FlatStyle.Flat;
            this.companyAdministrationButton.BackColor = Color.White;
            this.companyAdministrationButton.UseVisualStyleBackColor = false;
            this.companyAdministrationButton.FlatAppearance.BorderColor = Color.FromArgb(210, 221, 237);
            this.companyAdministrationButton.Click += this.companyAdministrationButton_Click;
            // documentsAndCommunicationButton
            this.documentsAndCommunicationButton.Location = new Point(430, 232);
            this.documentsAndCommunicationButton.Size = new Size(284, 43);
            this.documentsAndCommunicationButton.Name = "documentsAndCommunicationButton";
            this.documentsAndCommunicationButton.Text = "Documents & communication";
            this.documentsAndCommunicationButton.TextAlign = ContentAlignment.MiddleLeft;
            this.documentsAndCommunicationButton.Padding = new Padding(10, 0, 0, 0);
            this.documentsAndCommunicationButton.FlatStyle = FlatStyle.Flat;
            this.documentsAndCommunicationButton.BackColor = Color.White;
            this.documentsAndCommunicationButton.UseVisualStyleBackColor = false;
            this.documentsAndCommunicationButton.FlatAppearance.BorderColor = Color.FromArgb(210, 221, 237);
            this.documentsAndCommunicationButton.Click += this.documentsAndCommunicationButton_Click;
            // powerAppsButton
            this.powerAppsButton.Location = new Point(430, 281);
            this.powerAppsButton.Size = new Size(284, 43);
            this.powerAppsButton.Name = "powerAppsButton";
            this.powerAppsButton.Text = "Power Apps";
            this.powerAppsButton.TextAlign = ContentAlignment.MiddleLeft;
            this.powerAppsButton.Padding = new Padding(10, 0, 0, 0);
            this.powerAppsButton.FlatStyle = FlatStyle.Flat;
            this.powerAppsButton.BackColor = Color.White;
            this.powerAppsButton.UseVisualStyleBackColor = false;
            this.powerAppsButton.FlatAppearance.BorderColor = Color.FromArgb(210, 221, 237);
            this.powerAppsButton.Click += this.powerAppsButton_Click;
            // reportingAndCustomizationButton
            this.reportingAndCustomizationButton.Location = new Point(430, 330);
            this.reportingAndCustomizationButton.Size = new Size(284, 43);
            this.reportingAndCustomizationButton.Name = "reportingAndCustomizationButton";
            this.reportingAndCustomizationButton.Text = "Reporting & customization";
            this.reportingAndCustomizationButton.TextAlign = ContentAlignment.MiddleLeft;
            this.reportingAndCustomizationButton.Padding = new Padding(10, 0, 0, 0);
            this.reportingAndCustomizationButton.FlatStyle = FlatStyle.Flat;
            this.reportingAndCustomizationButton.BackColor = Color.White;
            this.reportingAndCustomizationButton.UseVisualStyleBackColor = false;
            this.reportingAndCustomizationButton.FlatAppearance.BorderColor = Color.FromArgb(210, 221, 237);
            this.reportingAndCustomizationButton.Click += this.reportingAndCustomizationButton_Click;
            // settingsButton
            this.settingsButton.Location = new Point(430, 379);
            this.settingsButton.Size = new Size(284, 43);
            this.settingsButton.Name = "settingsButton";
            this.settingsButton.Text = "Desktop connection settings";
            this.settingsButton.TextAlign = ContentAlignment.MiddleLeft;
            this.settingsButton.Padding = new Padding(10, 0, 0, 0);
            this.settingsButton.FlatStyle = FlatStyle.Flat;
            this.settingsButton.BackColor = Color.White;
            this.settingsButton.UseVisualStyleBackColor = false;
            this.settingsButton.FlatAppearance.BorderColor = Color.FromArgb(210, 221, 237);
            this.settingsButton.Click += this.settingsButton_Click;
            // companiesGridButton
            this.companiesGridButton.Location = new Point(430, 428);
            this.companiesGridButton.Size = new Size(284, 43);
            this.companiesGridButton.Name = "companiesGridButton";
            this.companiesGridButton.Text = "Local companies";
            this.companiesGridButton.TextAlign = ContentAlignment.MiddleLeft;
            this.companiesGridButton.Padding = new Padding(10, 0, 0, 0);
            this.companiesGridButton.FlatStyle = FlatStyle.Flat;
            this.companiesGridButton.BackColor = Color.White;
            this.companiesGridButton.UseVisualStyleBackColor = false;
            this.companiesGridButton.FlatAppearance.BorderColor = Color.FromArgb(210, 221, 237);
            this.companiesGridButton.Click += this.companiesGridButton_Click;
            this.Controls.Add(this.headingLabel);
            this.Controls.Add(this.modulesLabel);
            this.Controls.Add(this.sharedLabel);
            this.Controls.Add(this.appointmentsButton);
            this.Controls.Add(this.crmButton);
            this.Controls.Add(this.financeAndAccountingButton);
            this.Controls.Add(this.hrmsButton);
            this.Controls.Add(this.projectManagementButton);
            this.Controls.Add(this.salesAndPosButton);
            this.Controls.Add(this.businessDataButton);
            this.Controls.Add(this.companyAdministrationButton);
            this.Controls.Add(this.documentsAndCommunicationButton);
            this.Controls.Add(this.powerAppsButton);
            this.Controls.Add(this.reportingAndCustomizationButton);
            this.Controls.Add(this.settingsButton);
            this.Controls.Add(this.companiesGridButton);
            this.AutoScaleDimensions = new SizeF(96F, 96F);
            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.BackColor = Color.FromArgb(243, 246, 251);
            this.Font = new Font("Segoe UI", 10F);
            this.Text = "Business Suite";
            this.ClientSize = new Size(860, 490);
            this.MinimumSize = new Size(770, 530);
            this.StartPosition = FormStartPosition.CenterScreen;
            this.Name = "MainForm";
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Label headingLabel;
        private Label modulesLabel;
        private Label sharedLabel;
        private Button appointmentsButton;
        private Button crmButton;
        private Button financeAndAccountingButton;
        private Button hrmsButton;
        private Button projectManagementButton;
        private Button salesAndPosButton;
        private Button businessDataButton;
        private Button companyAdministrationButton;
        private Button documentsAndCommunicationButton;
        private Button powerAppsButton;
        private Button reportingAndCustomizationButton;
        private Button settingsButton;
        private Button companiesGridButton;
    }
}
