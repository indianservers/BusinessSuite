#nullable disable
using System;
using System.Drawing;
using System.Windows.Forms;

namespace Business_Suite
{
    partial class LeadConversionForm
    {
        private void InitializeComponent()
        {
            this.heading = new Label();
            this.customerTypeLabel = new Label();
            this.customerTypeBox = new ComboBox();
            this.companyLabel = new Label();
            this.companyBox = new ComboBox();
            this.contactLabel = new Label();
            this.contactBox = new ComboBox();
            this.dealCheck = new CheckBox();
            this.dealLabel = new Label();
            this.dealBox = new TextBox();
            this.feedback = new Label();
            this.convertButton = new Button();
            this.cancelButton = new Button();
            this.SuspendLayout();
            // heading
            this.heading.Location = new Point(21, 16);
            this.heading.Size = new Size(645, 48);
            this.heading.Name = "heading";
            this.heading.Text = "Convert lead";
            this.heading.Font = new Font("Segoe UI Semibold", 24F);
            // customerTypeLabel
            this.customerTypeLabel.Location = new Point(22, 80);
            this.customerTypeLabel.Size = new Size(620, 22);
            this.customerTypeLabel.Name = "customerTypeLabel";
            this.customerTypeLabel.Text = "Customer type";
            // customerTypeBox
            this.customerTypeBox.Location = new Point(22, 104);
            this.customerTypeBox.Size = new Size(618, 27);
            this.customerTypeBox.Name = "customerTypeBox";
            this.customerTypeBox.DropDownStyle = ComboBoxStyle.DropDownList;
            // companyLabel
            this.companyLabel.Location = new Point(22, 143);
            this.companyLabel.Size = new Size(620, 22);
            this.companyLabel.Name = "companyLabel";
            this.companyLabel.Text = "Company";
            // companyBox
            this.companyBox.Location = new Point(22, 167);
            this.companyBox.Size = new Size(618, 27);
            this.companyBox.Name = "companyBox";
            this.companyBox.DropDownStyle = ComboBoxStyle.DropDownList;
            // contactLabel
            this.contactLabel.Location = new Point(22, 205);
            this.contactLabel.Size = new Size(620, 22);
            this.contactLabel.Name = "contactLabel";
            this.contactLabel.Text = "Contact";
            // contactBox
            this.contactBox.Location = new Point(22, 229);
            this.contactBox.Size = new Size(618, 27);
            this.contactBox.Name = "contactBox";
            this.contactBox.DropDownStyle = ComboBoxStyle.DropDownList;
            // dealCheck
            this.dealCheck.Location = new Point(22, 271);
            this.dealCheck.Size = new Size(620, 30);
            this.dealCheck.Name = "dealCheck";
            this.dealCheck.Text = "Create an opportunity in the sales pipeline";
            this.dealCheck.Checked = true;
            this.dealCheck.CheckedChanged += this.DealChanged;
            // dealLabel
            this.dealLabel.Location = new Point(22, 309);
            this.dealLabel.Size = new Size(620, 22);
            this.dealLabel.Name = "dealLabel";
            this.dealLabel.Text = "Opportunity name";
            // dealBox
            this.dealBox.Location = new Point(22, 334);
            this.dealBox.Size = new Size(618, 28);
            this.dealBox.Name = "dealBox";
            this.dealBox.MaxLength = 180;
            // feedback
            this.feedback.Location = new Point(22, 371);
            this.feedback.Size = new Size(618, 48);
            this.feedback.Name = "feedback";
            this.feedback.Text = "";
            // convertButton
            this.convertButton.Location = new Point(417, 431);
            this.convertButton.Size = new Size(105, 39);
            this.convertButton.Name = "convertButton";
            this.convertButton.Text = "Convert";
            this.convertButton.Enabled = false;
            this.convertButton.Click += this.ConvertClicked;
            // cancelButton
            this.cancelButton.Location = new Point(535, 431);
            this.cancelButton.Size = new Size(105, 39);
            this.cancelButton.Name = "cancelButton";
            this.cancelButton.Text = "Cancel";
            this.cancelButton.DialogResult = DialogResult.Cancel;
            this.customerTypeBox.Items.AddRange(new object[] { "Individual", "Business" });
            this.Shown += this.ConversionShown;
            this.FormClosing += this.ConversionClosing;
            this.FormClosed += this.ConversionClosed;
            this.Controls.Add(this.heading);
            this.Controls.Add(this.customerTypeLabel);
            this.Controls.Add(this.customerTypeBox);
            this.Controls.Add(this.companyLabel);
            this.Controls.Add(this.companyBox);
            this.Controls.Add(this.contactLabel);
            this.Controls.Add(this.contactBox);
            this.Controls.Add(this.dealCheck);
            this.Controls.Add(this.dealLabel);
            this.Controls.Add(this.dealBox);
            this.Controls.Add(this.feedback);
            this.Controls.Add(this.convertButton);
            this.Controls.Add(this.cancelButton);
            this.AutoScaleDimensions = new SizeF(96F, 96F);
            this.AutoScaleMode = AutoScaleMode.Dpi;
            this.Font = new Font("Segoe UI", 10F);
            this.BackColor = Color.FromArgb(243, 246, 251);
            this.ForeColor = Color.FromArgb(24, 35, 58);
            this.Text = "Business Suite | Convert lead";
            this.ClientSize = new Size(663, 492);
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;
            this.StartPosition = FormStartPosition.CenterParent;
            this.AcceptButton = this.convertButton;
            this.CancelButton = this.cancelButton;
            this.Name = "LeadConversionForm";
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private Label heading;
        private Label customerTypeLabel;
        private ComboBox customerTypeBox;
        private Label companyLabel;
        private ComboBox companyBox;
        private Label contactLabel;
        private ComboBox contactBox;
        private CheckBox dealCheck;
        private Label dealLabel;
        private TextBox dealBox;
        private Label feedback;
        private Button convertButton;
        private Button cancelButton;
    }
}
