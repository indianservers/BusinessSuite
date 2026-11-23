#nullable disable
using System.ComponentModel;
using System.Drawing;
using System.Windows.Forms;
using Telerik.WinControls.UI;

namespace Business_Suite;

partial class EmailTemplateForm
{
    private void InitializeComponent()
    {
        this.nameLabel = new Label();
        this.nameBox = new RadTextBox();
        this.subjectLabel = new Label();
        this.subjectBox = new RadTextBox();
        this.bodyLabel = new Label();
        this.bodyBox = new RadTextBox();
        this.statusLabel = new Label();
        this.saveButton = new RadButton();
        this.cancelButton = new RadButton();
        ((ISupportInitialize)this.nameBox).BeginInit();
        ((ISupportInitialize)this.subjectBox).BeginInit();
        ((ISupportInitialize)this.bodyBox).BeginInit();
        ((ISupportInitialize)this.saveButton).BeginInit();
        ((ISupportInitialize)this.cancelButton).BeginInit();
        this.SuspendLayout();

        this.nameLabel.Name = "nameLabel";
        this.nameLabel.Text = "Template name";
        this.nameLabel.Location = new Point(18, 18);
        this.nameLabel.Size = new Size(550, 26);
        this.nameBox.Name = "nameBox";
        this.nameBox.AccessibleName = "Template name";
        this.nameBox.Location = new Point(18, 47);
        this.nameBox.Size = new Size(636, 29);
        this.nameBox.MaxLength = 180;
        this.nameBox.TabIndex = 0;

        this.subjectLabel.Name = "subjectLabel";
        this.subjectLabel.Text = "Subject";
        this.subjectLabel.Location = new Point(18, 87);
        this.subjectLabel.Size = new Size(550, 26);
        this.subjectBox.Name = "subjectBox";
        this.subjectBox.AccessibleName = "Subject";
        this.subjectBox.Location = new Point(18, 116);
        this.subjectBox.Size = new Size(636, 29);
        this.subjectBox.MaxLength = 240;
        this.subjectBox.TabIndex = 1;

        this.bodyLabel.Name = "bodyLabel";
        this.bodyLabel.Text = "Template content";
        this.bodyLabel.Location = new Point(18, 156);
        this.bodyLabel.Size = new Size(550, 26);
        this.bodyBox.Name = "bodyBox";
        this.bodyBox.AccessibleName = "Template content";
        this.bodyBox.Location = new Point(18, 185);
        this.bodyBox.Size = new Size(636, 182);
        this.bodyBox.MaxLength = 20000;
        this.bodyBox.TabIndex = 2;
        this.bodyBox.Multiline = true;
        this.bodyBox.ScrollBars = ScrollBars.Vertical;
        this.bodyBox.AcceptsReturn = true;

        this.statusLabel.Name = "statusLabel";
        this.statusLabel.Location = new Point(18, 378);
        this.statusLabel.Size = new Size(636, 46);

        this.saveButton.Name = "saveButton";
        this.saveButton.Text = "Save template";
        this.saveButton.Location = new Point(418, 435);
        this.saveButton.Size = new Size(130, 32);
        this.saveButton.TabIndex = 3;
        this.saveButton.Click += this.SaveClicked;

        this.cancelButton.Name = "cancelButton";
        this.cancelButton.Text = "Cancel";
        this.cancelButton.Location = new Point(556, 435);
        this.cancelButton.Size = new Size(98, 32);
        this.cancelButton.TabIndex = 4;
        this.cancelButton.DialogResult = DialogResult.Cancel;

        this.Controls.Add(this.nameLabel);
        this.Controls.Add(this.nameBox);
        this.Controls.Add(this.subjectLabel);
        this.Controls.Add(this.subjectBox);
        this.Controls.Add(this.bodyLabel);
        this.Controls.Add(this.bodyBox);
        this.Controls.Add(this.statusLabel);
        this.Controls.Add(this.saveButton);
        this.Controls.Add(this.cancelButton);
        this.AcceptButton = this.saveButton;
        this.CancelButton = this.cancelButton;
        this.AutoScaleDimensions = new SizeF(96F, 96F);
        this.AutoScaleMode = AutoScaleMode.Dpi;
        this.ClientSize = new Size(672, 486);
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.StartPosition = FormStartPosition.CenterParent;
        this.MaximizeBox = false;
        this.MinimizeBox = false;
        this.ShowInTaskbar = false;
        this.BackColor = Color.FromArgb(243, 246, 251);
        this.Font = new Font("Segoe UI", 10F);
        this.Text = "Email template";
        this.Name = "EmailTemplateForm";
        this.FormClosing += this.EditorClosing;
        ((ISupportInitialize)this.nameBox).EndInit();
        ((ISupportInitialize)this.subjectBox).EndInit();
        ((ISupportInitialize)this.bodyBox).EndInit();
        ((ISupportInitialize)this.saveButton).EndInit();
        ((ISupportInitialize)this.cancelButton).EndInit();
        this.ResumeLayout(false);
        this.PerformLayout();
    }

    private Label nameLabel;
    private RadTextBox nameBox;
    private Label subjectLabel;
    private RadTextBox subjectBox;
    private Label bodyLabel;
    private RadTextBox bodyBox;
    private Label statusLabel;
    private RadButton saveButton;
    private RadButton cancelButton;
}
