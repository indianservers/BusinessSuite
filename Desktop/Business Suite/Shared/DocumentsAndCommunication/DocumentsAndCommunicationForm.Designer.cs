#nullable disable
using System;
using System.Drawing;
using System.Windows.Forms;

namespace Business_Suite
{
    partial class DocumentsAndCommunicationForm
    {
        private void InitializeComponent()
        {
            this.headingLabel = new Label();
            this.descriptionLabel = new Label();
            this.communicationHubButton = new Button();
            this.crmFilesButton = new Button();
            this.SuspendLayout();
            // headingLabel
            this.headingLabel.Location = new Point(24, 24);
            this.headingLabel.Size = new Size(550, 43);
            this.headingLabel.Name = "headingLabel";
            this.headingLabel.Text = "Documents & communication";
            this.headingLabel.Font = new Font("Segoe UI Semibold", 21F);
            // descriptionLabel
            this.descriptionLabel.Location = new Point(24, 74);
            this.descriptionLabel.Size = new Size(550, 31);
            this.descriptionLabel.Name = "descriptionLabel";
            this.descriptionLabel.Text = "CRM communication and workspace documents.";
            // communicationHubButton
            this.communicationHubButton.Location = new Point(24, 112);
            this.communicationHubButton.Size = new Size(240, 42);
            this.communicationHubButton.Name = "communicationHubButton";
            this.communicationHubButton.Text = "Communication hub";
            this.communicationHubButton.FlatStyle = FlatStyle.Flat;
            this.communicationHubButton.BackColor = Color.White;
            this.communicationHubButton.UseVisualStyleBackColor = false;
            this.communicationHubButton.TabIndex = 0;
            this.communicationHubButton.Click += this.communicationHubButton_Click;
            // crmFilesButton
            this.crmFilesButton.Location = new Point(282, 112);
            this.crmFilesButton.Size = new Size(240, 42);
            this.crmFilesButton.Name = "crmFilesButton";
            this.crmFilesButton.Text = "CRM files";
            this.crmFilesButton.FlatStyle = FlatStyle.Flat;
            this.crmFilesButton.BackColor = Color.White;
            this.crmFilesButton.UseVisualStyleBackColor = false;
            this.crmFilesButton.TabIndex = 1;
            this.crmFilesButton.Click += this.crmFilesButton_Click;
            this.Controls.Add(this.headingLabel);
            this.Controls.Add(this.descriptionLabel);
            this.Controls.Add(this.communicationHubButton);
            this.Controls.Add(this.crmFilesButton);
            this.AutoScaleDimensions = new SizeF(96F, 96F);
            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.ClientSize = new Size(600, 350);
            this.StartPosition = FormStartPosition.CenterParent;
            this.BackColor = Color.FromArgb(243, 246, 251);
            this.Font = new Font("Segoe UI", 10F);
            this.Text = "Business Suite | Documents & communication";
            this.Name = "DocumentsAndCommunicationForm";
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Label headingLabel;
        private Label descriptionLabel;
        private Button communicationHubButton;
        private Button crmFilesButton;
    }
}
