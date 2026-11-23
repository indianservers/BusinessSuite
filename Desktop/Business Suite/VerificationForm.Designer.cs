#nullable disable
using System;
using System.Drawing;
using System.Windows.Forms;

namespace Business_Suite
{
    partial class VerificationForm
    {
        private void InitializeComponent()
        {
            this.code = new CueTextBox();
            this.recovery = new CheckBox();
            this.verify = new Button();
            this.SuspendLayout();
            // code
            this.code.Location = new Point(18, 16);
            this.code.Size = new Size(374, 30);
            this.code.Name = "code";
            this.code.AccessibleName = "Verification code";
            this.code.PlaceholderText = "Verification code";
            this.code.UseSystemPasswordChar = true;
            this.code.MaxLength = 128;
            // recovery
            this.recovery.Location = new Point(18, 53);
            this.recovery.Size = new Size(374, 28);
            this.recovery.Name = "recovery";
            this.recovery.Text = "Use a recovery code";
            // verify
            this.verify.Location = new Point(278, 95);
            this.verify.Size = new Size(114, 40);
            this.verify.Name = "verify";
            this.verify.Text = "Verify";
            this.verify.DialogResult = DialogResult.OK;
            this.Controls.Add(this.code);
            this.Controls.Add(this.recovery);
            this.Controls.Add(this.verify);
            this.AutoScaleDimensions = new SizeF(96F, 96F);
            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.Font = new Font("Segoe UI", 10F);
            this.BackColor = Color.FromArgb(243, 246, 251);
            this.ForeColor = Color.FromArgb(24, 35, 58);
            this.StartPosition = FormStartPosition.CenterParent;
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;
            this.MinimizeBox = false;
            this.Text = "Verification";
            this.ClientSize = new Size(410, 156);
            this.AcceptButton = this.verify;
            this.Name = "VerificationForm";
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private CueTextBox code;
        private CheckBox recovery;
        private Button verify;
    }
}
