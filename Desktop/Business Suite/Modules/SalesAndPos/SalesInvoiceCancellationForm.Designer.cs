using System.ComponentModel;
using Telerik.WinControls.UI;

namespace Business_Suite;

partial class SalesInvoiceCancellationForm
{
    private void InitializeComponent()
    {
        this.headingLabel = new Label();
        this.instructionsLabel = new Label();
        this.reasonLabel = new Label();
        this.statusLabel = new Label();
        this.reasonBox = new RadTextBox();
        this.cancelInvoiceButton = new RadButton();
        this.closeButton = new RadButton();
        ((ISupportInitialize)this.reasonBox).BeginInit();
        ((ISupportInitialize)this.cancelInvoiceButton).BeginInit();
        ((ISupportInitialize)this.closeButton).BeginInit();
        this.SuspendLayout();

        this.headingLabel.Name = "headingLabel";
        this.headingLabel.Location = new Point(20, 16);
        this.headingLabel.Size = new Size(471, 34);
        this.headingLabel.Font = new Font("Segoe UI Semibold", 16F);
        this.headingLabel.Text = "Cancel invoice";

        this.instructionsLabel.Name = "instructionsLabel";
        this.instructionsLabel.Text = "Reverse applied payments and posted vouchers through Accounting first. The original billing source stays reserved.";
        this.instructionsLabel.Location = new Point(20, 57);
        this.instructionsLabel.Size = new Size(471, 45);

        this.reasonLabel.Name = "reasonLabel";
        this.reasonLabel.Text = "Cancellation reason";
        this.reasonLabel.Location = new Point(20, 104);
        this.reasonLabel.Size = new Size(471, 19);

        this.reasonBox.Name = "reasonBox";
        this.reasonBox.AccessibleName = "Cancellation reason";
        this.reasonBox.Location = new Point(20, 126);
        this.reasonBox.Size = new Size(471, 86);
        this.reasonBox.Multiline = true;
        this.reasonBox.MaxLength = 500;
        this.reasonBox.TextChanged += this.ReasonChanged;

        this.statusLabel.Name = "statusLabel";
        this.statusLabel.Location = new Point(20, 221);
        this.statusLabel.Size = new Size(471, 40);

        this.cancelInvoiceButton.Name = "cancelInvoiceButton";
        this.cancelInvoiceButton.Text = "Cancel invoice";
        this.cancelInvoiceButton.Location = new Point(238, 270);
        this.cancelInvoiceButton.Size = new Size(139, 30);
        this.cancelInvoiceButton.Enabled = false;
        this.cancelInvoiceButton.Click += this.CancelInvoiceClicked;

        this.closeButton.Name = "closeButton";
        this.closeButton.Text = "Keep invoice";
        this.closeButton.Location = new Point(386, 270);
        this.closeButton.Size = new Size(105, 30);
        this.closeButton.DialogResult = DialogResult.Cancel;

        this.AutoScaleDimensions = new SizeF(7F, 15F);
        this.AutoScaleMode = AutoScaleMode.Font;
        this.ClientSize = new Size(511, 323);
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.MaximizeBox = false;
        this.MinimizeBox = false;
        this.Controls.Add(this.headingLabel);
        this.Controls.Add(this.instructionsLabel);
        this.Controls.Add(this.reasonLabel);
        this.Controls.Add(this.reasonBox);
        this.Controls.Add(this.statusLabel);
        this.Controls.Add(this.cancelInvoiceButton);
        this.Controls.Add(this.closeButton);
        this.StartPosition = FormStartPosition.CenterParent;
        this.CancelButton = this.closeButton;
        this.Name = "SalesInvoiceCancellationForm";
        this.Text = "Cancel invoice";
        this.FormClosing += this.CancellationClosing;
        ((ISupportInitialize)this.reasonBox).EndInit();
        ((ISupportInitialize)this.cancelInvoiceButton).EndInit();
        ((ISupportInitialize)this.closeButton).EndInit();
        this.ResumeLayout(false);
    }

    private Label headingLabel;
    private Label instructionsLabel;
    private Label reasonLabel;
    private Label statusLabel;
    private RadTextBox reasonBox;
    private RadButton cancelInvoiceButton;
    private RadButton closeButton;
}
