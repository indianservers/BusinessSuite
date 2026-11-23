#nullable disable
using System.Drawing;
using System.Windows.Forms;

namespace Business_Suite
{
    partial class CrmRecordForm
    {
        private void InitializeComponent()
        {
            this.headingLabel = new Label();
            this.detailsBox = new TextBox();
            this.SuspendLayout();
            this.headingLabel.Location = new Point(22, 20);
            this.headingLabel.Size = new Size(625, 45);
            this.headingLabel.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            this.headingLabel.AutoEllipsis = true;
            this.headingLabel.Font = new Font("Segoe UI Semibold", 22F);
            this.headingLabel.Name = "headingLabel";
            this.headingLabel.Text = "CRM record";
            this.detailsBox.Location = new Point(22, 73);
            this.detailsBox.Size = new Size(625, 416);
            this.detailsBox.Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
            this.detailsBox.Name = "detailsBox";
            this.detailsBox.Multiline = true;
            this.detailsBox.ReadOnly = true;
            this.detailsBox.ScrollBars = ScrollBars.Vertical;
            this.detailsBox.AccessibleName = "CRM record details";
            this.AutoScaleDimensions = new SizeF(96F, 96F);
            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.BackColor = Color.FromArgb(243, 246, 251);
            this.ClientSize = new Size(670, 510);
            this.Controls.Add(this.headingLabel);
            this.Controls.Add(this.detailsBox);
            this.Font = new Font("Segoe UI", 10F);
            this.MinimumSize = new Size(450, 380);
            this.Name = "CrmRecordForm";
            this.StartPosition = FormStartPosition.CenterParent;
            this.Text = "Business Suite | CRM record";
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Label headingLabel;
        private TextBox detailsBox;
    }
}
