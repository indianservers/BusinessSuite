#nullable disable
using System.ComponentModel;
using System.Drawing;
using System.Windows.Forms;
using Telerik.WinControls.UI;

namespace Business_Suite;

partial class PosClosingForm
{
    private void InitializeComponent()
    {
        this.totalsLabel = new Label();
        this.countLabel = new Label();
        this.countBox = new RadTextBox();
        this.notesLabel = new Label();
        this.notesBox = new RadTextBox();
        this.statusLabel = new Label();
        this.postButton = new RadButton();
        this.cancelButton = new RadButton();
        ((ISupportInitialize)this.countBox).BeginInit();
        ((ISupportInitialize)this.notesBox).BeginInit();
        ((ISupportInitialize)this.postButton).BeginInit();
        ((ISupportInitialize)this.cancelButton).BeginInit();
        this.SuspendLayout();

        this.totalsLabel.Name = "totalsLabel";
        this.totalsLabel.Location = new Point(16, 14);
        this.totalsLabel.Size = new Size(575, 68);
        this.countLabel.Name = "countLabel";
        this.countLabel.Location = new Point(16, 91);
        this.countLabel.Size = new Size(155, 24);
        this.countLabel.Text = "Counted cash";
        this.countBox.Name = "countBox";
        this.countBox.Location = new Point(180, 87);
        this.countBox.Size = new Size(211, 27);
        this.notesLabel.Name = "notesLabel";
        this.notesLabel.Location = new Point(16, 132);
        this.notesLabel.Size = new Size(155, 26);
        this.notesLabel.Text = "Notes";
        this.notesBox.Name = "notesBox";
        this.notesBox.Location = new Point(16, 160);
        this.notesBox.Size = new Size(575, 93);
        this.statusLabel.Name = "statusLabel";
        this.statusLabel.Location = new Point(16, 262);
        this.statusLabel.Size = new Size(575, 48);
        this.postButton.Name = "postButton";
        this.postButton.Location = new Point(328, 319);
        this.postButton.Size = new Size(140, 30);
        this.postButton.Text = "Post closing";
        this.cancelButton.Name = "cancelButton";
        this.cancelButton.Location = new Point(478, 319);
        this.cancelButton.Size = new Size(113, 30);
        this.cancelButton.Text = "Cancel";
        this.countBox.AccessibleName = "Counted cash";
        this.countBox.MaxLength = 24;
        this.countBox.TextChanged += this.CountChanged;
        this.notesBox.AccessibleName = "Closing notes";
        this.notesBox.Multiline = true;
        this.notesBox.MaxLength = 500;
        this.notesBox.ScrollBars = ScrollBars.Vertical;
        this.cancelButton.DialogResult = DialogResult.Cancel;
        this.postButton.Click += this.PostClosing;

        this.Controls.Add(this.totalsLabel);
        this.Controls.Add(this.countLabel);
        this.Controls.Add(this.countBox);
        this.Controls.Add(this.notesLabel);
        this.Controls.Add(this.notesBox);
        this.Controls.Add(this.statusLabel);
        this.Controls.Add(this.postButton);
        this.Controls.Add(this.cancelButton);
        this.AcceptButton = this.postButton;
        this.CancelButton = this.cancelButton;
        this.ClientSize = new Size(607, 365);
        this.StartPosition = FormStartPosition.CenterParent;
        this.AutoScaleDimensions = new SizeF(96F, 96F);
        this.AutoScaleMode = AutoScaleMode.Dpi;
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.Font = new Font("Segoe UI", 10F);
        this.BackColor = Color.FromArgb(243, 246, 251);
        this.MaximizeBox = false;
        this.MinimizeBox = false;
        this.ShowInTaskbar = false;
        this.Name = "PosClosingForm";
        this.Text = "Cashier closing";
        this.FormClosing += this.ClosingFormClosing;

        ((ISupportInitialize)this.countBox).EndInit();
        ((ISupportInitialize)this.notesBox).EndInit();
        ((ISupportInitialize)this.postButton).EndInit();
        ((ISupportInitialize)this.cancelButton).EndInit();
        this.ResumeLayout(false);
        this.PerformLayout();
    }

    private Label totalsLabel;
    private Label countLabel;
    private RadTextBox countBox;
    private Label notesLabel;
    private RadTextBox notesBox;
    private Label statusLabel;
    private RadButton postButton;
    private RadButton cancelButton;
}
