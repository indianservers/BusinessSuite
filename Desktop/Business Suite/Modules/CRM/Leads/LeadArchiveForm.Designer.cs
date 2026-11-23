#nullable disable
using System;
using System.Drawing;
using System.Windows.Forms;

namespace Business_Suite
{
    partial class LeadArchiveForm
    {
        private void InitializeComponent()
        {
            this.nameLabel = new Label();
            this.reasonLabel = new Label();
            this.reasonBox = new TextBox();
            this.archiveButton = new Button();
            this.cancelButton = new Button();
            this.SuspendLayout();
            // nameLabel
            this.nameLabel.Location = new Point(18, 14);
            this.nameLabel.Size = new Size(478, 40);
            this.nameLabel.Name = "nameLabel";
            this.nameLabel.Text = "Archive lead";
            this.nameLabel.Font = new Font("Segoe UI Semibold", 16F);
            // reasonLabel
            this.reasonLabel.Location = new Point(18, 64);
            this.reasonLabel.Size = new Size(478, 24);
            this.reasonLabel.Name = "reasonLabel";
            this.reasonLabel.Text = "Reason for archiving";
            // reasonBox
            this.reasonBox.Location = new Point(18, 92);
            this.reasonBox.Size = new Size(478, 85);
            this.reasonBox.Name = "reasonBox";
            this.reasonBox.Multiline = true;
            this.reasonBox.MaxLength = 1000;
            this.reasonBox.AccessibleName = "Archive reason";
            this.reasonBox.TextChanged += this.ReasonChanged;
            // archiveButton
            this.archiveButton.Location = new Point(281, 194);
            this.archiveButton.Size = new Size(100, 38);
            this.archiveButton.Name = "archiveButton";
            this.archiveButton.Text = "Archive";
            this.archiveButton.Enabled = false;
            this.archiveButton.DialogResult = DialogResult.OK;
            // cancelButton
            this.cancelButton.Location = new Point(396, 194);
            this.cancelButton.Size = new Size(100, 38);
            this.cancelButton.Name = "cancelButton";
            this.cancelButton.Text = "Cancel";
            this.cancelButton.DialogResult = DialogResult.Cancel;
            this.Controls.Add(this.nameLabel);
            this.Controls.Add(this.reasonLabel);
            this.Controls.Add(this.reasonBox);
            this.Controls.Add(this.archiveButton);
            this.Controls.Add(this.cancelButton);
            this.AutoScaleDimensions = new SizeF(96F, 96F);
            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.Font = new Font("Segoe UI", 10F);
            this.BackColor = Color.FromArgb(243, 246, 251);
            this.ForeColor = Color.FromArgb(24, 35, 58);
            this.ClientSize = new Size(514, 250);
            this.StartPosition = FormStartPosition.CenterParent;
            this.MaximizeBox = false;
            this.MinimizeBox = false;
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.Text = "Business Suite | Archive lead";
            this.AcceptButton = this.archiveButton;
            this.CancelButton = this.cancelButton;
            this.Name = "LeadArchiveForm";
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Label nameLabel;
        private Label reasonLabel;
        private TextBox reasonBox;
        private Button archiveButton;
        private Button cancelButton;
    }
}
