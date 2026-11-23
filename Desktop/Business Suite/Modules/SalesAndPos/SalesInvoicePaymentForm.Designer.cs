using System.ComponentModel;
using Telerik.WinControls;
using Telerik.WinControls.UI;

namespace Business_Suite;

partial class SalesInvoicePaymentForm
{
    private void InitializeComponent()
    {
        this.headingLabel = new Label();
        this.balanceLabel = new Label();
        this.amountLabel = new Label();
        this.methodLabel = new Label();
        this.dateLabel = new Label();
        this.referenceLabel = new Label();
        this.statusLabel = new Label();
        this.amountEditor = new RadSpinEditor();
        this.methodPicker = new RadDropDownList();
        this.datePicker = new RadDateTimePicker();
        this.referenceBox = new RadTextBox();
        this.saveButton = new RadButton();
        this.cancelButton = new RadButton();
        ((ISupportInitialize)this.amountEditor).BeginInit();
        ((ISupportInitialize)this.methodPicker).BeginInit();
        ((ISupportInitialize)this.datePicker).BeginInit();
        ((ISupportInitialize)this.referenceBox).BeginInit();
        ((ISupportInitialize)this.saveButton).BeginInit();
        ((ISupportInitialize)this.cancelButton).BeginInit();
        this.SuspendLayout();

        this.headingLabel.Name = "headingLabel";
        this.headingLabel.Location = new Point(22, 17);
        this.headingLabel.Size = new Size(476, 32);
        this.headingLabel.Font = new Font("Segoe UI Semibold", 16F);
        this.headingLabel.Text = "Record invoice payment";

        this.balanceLabel.Name = "balanceLabel";
        this.balanceLabel.Location = new Point(22, 52);
        this.balanceLabel.Size = new Size(476, 24);

        this.amountLabel.Name = "amountLabel";
        this.amountLabel.Text = "Amount received";
        this.amountLabel.Location = new Point(22, 88);
        this.amountLabel.Size = new Size(150, 21);
        this.amountEditor.Name = "amountEditor";
        this.amountEditor.AccessibleName = "Amount received";
        this.amountEditor.Location = new Point(180, 87);
        this.amountEditor.Size = new Size(310, 27);
        this.amountEditor.DecimalPlaces = 2;
        this.amountEditor.Maximum = 99999999999M;
        this.amountEditor.Increment = 0.01M;

        this.methodLabel.Name = "methodLabel";
        this.methodLabel.Text = "Payment method";
        this.methodLabel.Location = new Point(22, 123);
        this.methodLabel.Size = new Size(150, 21);
        this.methodPicker.Name = "methodPicker";
        this.methodPicker.AccessibleName = "Payment method";
        this.methodPicker.Location = new Point(180, 122);
        this.methodPicker.Size = new Size(310, 27);
        this.methodPicker.DropDownStyle = RadDropDownStyle.DropDownList;

        this.dateLabel.Name = "dateLabel";
        this.dateLabel.Text = "Received on";
        this.dateLabel.Location = new Point(22, 158);
        this.dateLabel.Size = new Size(150, 21);
        this.datePicker.Name = "datePicker";
        this.datePicker.AccessibleName = "Received on";
        this.datePicker.Location = new Point(180, 157);
        this.datePicker.Size = new Size(310, 27);
        this.datePicker.Format = DateTimePickerFormat.Short;

        this.referenceLabel.Name = "referenceLabel";
        this.referenceLabel.Text = "Bank / payment reference";
        this.referenceLabel.Location = new Point(22, 193);
        this.referenceLabel.Size = new Size(155, 23);
        this.referenceBox.Name = "referenceBox";
        this.referenceBox.AccessibleName = "Bank or payment reference";
        this.referenceBox.Location = new Point(180, 192);
        this.referenceBox.Size = new Size(310, 27);
        this.referenceBox.MaxLength = 120;

        this.statusLabel.Name = "statusLabel";
        this.statusLabel.Location = new Point(22, 238);
        this.statusLabel.Size = new Size(468, 48);

        this.saveButton.Name = "saveButton";
        this.saveButton.Text = "Record received payment";
        this.saveButton.Location = new Point(206, 299);
        this.saveButton.Size = new Size(175, 28);
        this.saveButton.Enabled = false;
        this.saveButton.Click += this.SaveClicked;

        this.cancelButton.Name = "cancelButton";
        this.cancelButton.Text = "Close";
        this.cancelButton.Location = new Point(390, 299);
        this.cancelButton.Size = new Size(100, 28);
        this.cancelButton.DialogResult = DialogResult.Cancel;

        this.AutoScaleDimensions = new SizeF(7F, 15F);
        this.AutoScaleMode = AutoScaleMode.Font;
        this.ClientSize = new Size(512, 348);
        this.FormBorderStyle = FormBorderStyle.FixedDialog;
        this.MaximizeBox = false;
        this.MinimizeBox = false;
        this.Controls.Add(this.headingLabel);
        this.Controls.Add(this.balanceLabel);
        this.Controls.Add(this.amountLabel);
        this.Controls.Add(this.amountEditor);
        this.Controls.Add(this.methodLabel);
        this.Controls.Add(this.methodPicker);
        this.Controls.Add(this.dateLabel);
        this.Controls.Add(this.datePicker);
        this.Controls.Add(this.referenceLabel);
        this.Controls.Add(this.referenceBox);
        this.Controls.Add(this.statusLabel);
        this.Controls.Add(this.saveButton);
        this.Controls.Add(this.cancelButton);
        this.CancelButton = this.cancelButton;
        this.StartPosition = FormStartPosition.CenterParent;
        this.Name = "SalesInvoicePaymentForm";
        this.Text = "Record invoice payment";
        this.Shown += this.PaymentShown;
        this.FormClosing += this.PaymentClosing;
        this.FormClosed += this.PaymentClosed;
        ((ISupportInitialize)this.amountEditor).EndInit();
        ((ISupportInitialize)this.methodPicker).EndInit();
        ((ISupportInitialize)this.datePicker).EndInit();
        ((ISupportInitialize)this.referenceBox).EndInit();
        ((ISupportInitialize)this.saveButton).EndInit();
        ((ISupportInitialize)this.cancelButton).EndInit();
        this.ResumeLayout(false);
    }

    private Label headingLabel;
    private Label balanceLabel;
    private Label amountLabel;
    private Label methodLabel;
    private Label dateLabel;
    private Label referenceLabel;
    private Label statusLabel;
    private RadSpinEditor amountEditor;
    private RadDropDownList methodPicker;
    private RadDateTimePicker datePicker;
    private RadTextBox referenceBox;
    private RadButton saveButton;
    private RadButton cancelButton;
}
