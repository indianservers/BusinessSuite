#nullable disable
using System;
using System.Drawing;
using System.Windows.Forms;

namespace Business_Suite
{
    partial class ReportingAndCustomizationForm
    {
        private void InitializeComponent()
        {
            this.headingLabel = new Label();
            this.descriptionLabel = new Label();
            this.reportsButton = new Button();
            this.reportBuilderButton = new Button();
            this.settingsButton = new Button();
            this.SuspendLayout();
            // headingLabel
            this.headingLabel.Location = new Point(24, 24);
            this.headingLabel.Size = new Size(550, 43);
            this.headingLabel.Name = "headingLabel";
            this.headingLabel.Text = "Reporting & customization";
            this.headingLabel.Font = new Font("Segoe UI Semibold", 21F);
            // descriptionLabel
            this.descriptionLabel.Location = new Point(24, 74);
            this.descriptionLabel.Size = new Size(550, 31);
            this.descriptionLabel.Name = "descriptionLabel";
            this.descriptionLabel.Text = "Reports and business settings.";
            // reportsButton
            this.reportsButton.Location = new Point(24, 112);
            this.reportsButton.Size = new Size(240, 42);
            this.reportsButton.Name = "reportsButton";
            this.reportsButton.Text = "Reports";
            this.reportsButton.FlatStyle = FlatStyle.Flat;
            this.reportsButton.BackColor = Color.White;
            this.reportsButton.UseVisualStyleBackColor = false;
            this.reportsButton.TabIndex = 0;
            this.reportsButton.Click += this.reportsButton_Click;
            // reportBuilderButton
            this.reportBuilderButton.Location = new Point(282, 112);
            this.reportBuilderButton.Size = new Size(240, 42);
            this.reportBuilderButton.Name = "reportBuilderButton";
            this.reportBuilderButton.Text = "Report builder";
            this.reportBuilderButton.FlatStyle = FlatStyle.Flat;
            this.reportBuilderButton.BackColor = Color.White;
            this.reportBuilderButton.UseVisualStyleBackColor = false;
            this.reportBuilderButton.TabIndex = 1;
            this.reportBuilderButton.Click += this.reportBuilderButton_Click;
            // settingsButton
            this.settingsButton.Location = new Point(24, 164);
            this.settingsButton.Size = new Size(240, 42);
            this.settingsButton.Name = "settingsButton";
            this.settingsButton.Text = "Settings";
            this.settingsButton.FlatStyle = FlatStyle.Flat;
            this.settingsButton.BackColor = Color.White;
            this.settingsButton.UseVisualStyleBackColor = false;
            this.settingsButton.TabIndex = 2;
            this.settingsButton.Click += this.settingsButton_Click;
            this.Controls.Add(this.headingLabel);
            this.Controls.Add(this.descriptionLabel);
            this.Controls.Add(this.reportsButton);
            this.Controls.Add(this.reportBuilderButton);
            this.Controls.Add(this.settingsButton);
            this.AutoScaleDimensions = new SizeF(96F, 96F);
            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.ClientSize = new Size(600, 350);
            this.StartPosition = FormStartPosition.CenterParent;
            this.BackColor = Color.FromArgb(243, 246, 251);
            this.Font = new Font("Segoe UI", 10F);
            this.Text = "Business Suite | Reporting & customization";
            this.Name = "ReportingAndCustomizationForm";
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Label headingLabel;
        private Label descriptionLabel;
        private Button reportsButton;
        private Button reportBuilderButton;
        private Button settingsButton;
    }
}
